# -*- coding: utf-8 -*-
from datetime import date

from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase

from odoo.addons.rental_subrent.services.rental_subrent_margin_services import (
    calc_subrent_margin,
)
from odoo.addons.rental_subrent.services.rental_subrent_status_services import (
    get_subrent_kpis,
    shortage_for_product,
)


class TestSubrentLifecycle(TransactionCase):
    """Core A/B/D/E/G cases from plan matrix (ledger + buckets)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        company = cls.env.company
        cls.company = company
        cls.supplier = cls.env["res.partner"].create({
            "name": "NCC Subrent Test",
            "is_company": True,
            "customer_type": "company",
            "is_rental_supplier": True,
            "company_id": company.id,
        })
        cls.customer = cls.env["res.partner"].create({
            "name": "KH Subrent Test",
            "is_company": True,
            "customer_type": "company",
            "is_rental_customer": True,
            "company_id": company.id,
        })
        cls.customer_rep = cls.env["res.partner"].create({
            "name": "KH Rep",
            "parent_id": cls.customer.id,
        })
        cls.company_rep = cls.env["res.partner"].create({
            "name": "Co Rep",
            "parent_id": company.partner_id.id,
        })
        cls.driver = cls.env["res.partner"].create({
            "name": "Driver Subrent",
            "customer_type": "driver",
        })
        cls.truck = cls.env["transport.truck"].create({
            "name": "51A-SUB",
            "plate": "51A-SUB",
            "company_id": company.id,
        })
        cls.product = cls.env["product.product"].create({
            "name": "SP Thue Ngoai",
            "type": "product",
            "list_price": 3000.0,
        })
        cls.subrent_contract = cls.env["rental.subrent.contract"].create({
            "supplier_id": cls.supplier.id,
            "date_start": date(2026, 1, 1),
            "date_end": date(2026, 12, 31),
            "company_id": company.id,
            "policy_code": "tracked",
            "line_ids": [(0, 0, {
                "product_tmpl_id": cls.product.product_tmpl_id.id,
                "cost_unit": 1500.0,
                "minimum_rental_months": 0,
            })],
        })
        cls.subrent_contract.action_activate()
        cls.rental_contract = cls.env["rental.contract"].create({
            "name": "RC Subrent",
            "a_company_party": cls.customer.id,
            "a_party": cls.customer_rep.id,
            "b_company_party": company.partner_id.id,
            "b_party": cls.company_rep.id,
            "minimum_rental_months": 0,
        })
        cls.env["rental.contract.line"].create({
            "contract_id": cls.rental_contract.id,
            "product_tmpl_id": cls.product.product_tmpl_id.id,
            "price_unit": 3000.0,
        })
        cls.rental_contract.status = "active"

    def _receive(self, qty=10, when=None):
        when = when or date(2026, 1, 1)
        receipt = self.env["rental.subrent.receipt"].create({
            "subrent_contract_id": self.subrent_contract.id,
            "date": when,
            "stock_flow": "into_stock",
            "company_id": self.company.id,
            "line_ids": [(0, 0, {
                "product_id": self.product.id,
                "qty": qty,
            })],
        })
        receipt.action_confirm()
        return receipt.line_ids.lot_id

    def _transport(self, lot, transport_type, when, qty, state="done"):
        return self.env["rr.transport"].create({
            "rental_contract_id": self.rental_contract.id,
            "type": transport_type,
            "source_type": "subrent",
            "state": state,
            "start_rental_or_return_date": when,
            "driver_id": self.driver.id,
            "transport_truck_id": self.truck.id,
            "vehicle_start_time": when,
            "transport_line_ids": [(0, 0, {
                "product_id": self.product.id,
                "qty": qty,
                "subrent_lot_id": lot.id,
            })],
        })

    def test_a01_receive_into_stock_buckets(self):
        lot = self._receive(10)
        self.assertEqual(lot.qty_received, 10)
        self.assertEqual(lot.qty_at_subrent_wh, 10)
        self.assertEqual(lot.qty_on_customer, 0)
        self.assertEqual(lot.state, "open")
        loc = self.company._rental_subrent_stock_location()
        self.assertTrue(loc.is_rental_subrent_stock)

    def test_a03_receive_zero_qty_blocked(self):
        receipt = self.env["rental.subrent.receipt"].create({
            "subrent_contract_id": self.subrent_contract.id,
            "date": date(2026, 1, 1),
            "stock_flow": "into_stock",
            "company_id": self.company.id,
            "line_ids": [(0, 0, {"product_id": self.product.id, "qty": 0})],
        })
        with self.assertRaises(ValidationError):
            receipt.action_confirm()

    def test_a04_product_not_on_contract_blocked(self):
        other = self.env["product.product"].create({
            "name": "Other",
            "type": "product",
            "list_price": 100,
        })
        receipt = self.env["rental.subrent.receipt"].create({
            "subrent_contract_id": self.subrent_contract.id,
            "date": date(2026, 1, 1),
            "stock_flow": "into_stock",
            "company_id": self.company.id,
            "line_ids": [(0, 0, {"product_id": other.id, "qty": 1})],
        })
        with self.assertRaises(ValidationError):
            receipt.action_confirm()

    def test_b01_deliver_from_subrent_wh(self):
        lot = self._receive(10)
        self._transport(lot, "delivery", date(2026, 1, 5), 4)
        self.assertEqual(lot.qty_at_subrent_wh, 6)
        self.assertEqual(lot.qty_on_customer, 4)

    def test_b02_over_deliver_blocked(self):
        lot = self._receive(5)
        with self.assertRaises(ValidationError):
            self._transport(lot, "delivery", date(2026, 1, 5), 9)

    def test_c01_pass_through_dropship(self):
        lot = self.env["rental.subrent.lot"].create({
            "subrent_contract_id": self.subrent_contract.id,
            "product_id": self.product.id,
            "stock_flow": "pass_through",
            "cost_unit": 1500.0,
            "date_start": date(2026, 2, 1),
            "company_id": self.company.id,
        })
        self._transport(lot, "delivery", date(2026, 2, 1), 3)
        self.assertEqual(lot.qty_received, 3)
        self.assertEqual(lot.qty_on_customer, 3)
        self.assertEqual(lot.qty_at_subrent_wh, 0)

    def test_d01_customer_return_to_subrent_wh(self):
        lot = self._receive(10)
        self._transport(lot, "delivery", date(2026, 1, 5), 4)
        self._transport(lot, "return", date(2026, 1, 20), 2)
        self.assertEqual(lot.qty_on_customer, 2)
        self.assertEqual(lot.qty_at_subrent_wh, 8)

    def test_e01_return_to_supplier(self):
        lot = self._receive(10)
        ret = self.env["rental.subrent.return"].create({
            "subrent_contract_id": self.subrent_contract.id,
            "date": date(2026, 3, 1),
            "company_id": self.company.id,
            "line_ids": [(0, 0, {"lot_id": lot.id, "qty": 10})],
        })
        ret.action_confirm()
        self.assertEqual(lot.qty_at_subrent_wh, 0)
        self.assertEqual(lot.qty_returned_supplier, 10)
        self.assertEqual(lot.state, "closed")
        self.assertEqual(lot.date_end, date(2026, 3, 1))

    def test_e02_return_supplier_blocked_while_on_customer(self):
        lot = self._receive(10)
        self._transport(lot, "delivery", date(2026, 1, 5), 4)
        ret = self.env["rental.subrent.return"].create({
            "subrent_contract_id": self.subrent_contract.id,
            "date": date(2026, 3, 1),
            "company_id": self.company.id,
            "line_ids": [(0, 0, {"lot_id": lot.id, "qty": 6})],
        })
        with self.assertRaises(UserError):
            ret.action_confirm()

    def test_f02_lot_qty_readonly(self):
        lot = self._receive(5)
        with self.assertRaises(UserError):
            lot.write({"qty_at_subrent_wh": 99})

    def test_g02_kpis(self):
        lot = self._receive(10)
        self._transport(lot, "delivery", date(2026, 1, 5), 4)
        kpis = get_subrent_kpis(self.env, company_ids=[self.company.id])
        self.assertGreaterEqual(kpis["qty_at_subrent_wh"], 6)
        self.assertGreaterEqual(kpis["qty_on_customer"], 4)

    def test_g04_location_summary_split(self):
        lot = self._receive(10)
        self._transport(lot, "delivery", date(2026, 1, 5), 6)
        self.assertIn("Kho TN", lot.location_summary)
        self.assertIn("CT", lot.location_summary)

    def test_h01_margin_idle_cost(self):
        lot = self._receive(10, when=date(2026, 1, 1))
        # idle until deliver on Jan 10
        self._transport(lot, "delivery", date(2026, 1, 10), 10)
        rows = calc_subrent_margin(
            self.env, date(2026, 1, 1), date(2026, 1, 9), company_ids=[self.company.id]
        )
        row = next(r for r in rows if r["lot_id"] == lot.id)
        self.assertGreater(row["cost"], 0)
        self.assertEqual(row["revenue"], 0)

    def test_shortage_panel(self):
        self._receive(2)
        data = shortage_for_product(self.env, self.product, 10, self.company)
        self.assertEqual(data["subrent_wh_qty"], 2)
        self.assertGreaterEqual(data["shortage_qty"], 8)

    def test_b04_mixed_source_create_picking_blocked(self):
        lot = self._receive(5)
        transport = self.env["rr.transport"].create({
            "rental_contract_id": self.rental_contract.id,
            "type": "delivery",
            "source_type": "subrent",
            "state": "draft",
            "start_rental_or_return_date": date(2026, 1, 5),
            "driver_id": self.driver.id,
            "transport_truck_id": self.truck.id,
            "vehicle_start_time": date(2026, 1, 5),
            "transport_line_ids": [(0, 0, {
                "product_id": self.product.id,
                "qty": 1,
                # missing lot → blocked on create pickings
            })],
        })
        with self.assertRaises(UserError):
            transport.action_create_pickings()
        with self.assertRaises(UserError):
            transport.action_complete_transport()

    def test_ledger_immutable(self):
        lot = self._receive(1)
        led = lot.ledger_ids[:1]
        with self.assertRaises(UserError):
            led.write({"qty": 99})
