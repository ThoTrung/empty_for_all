# -*- coding: utf-8 -*-
from datetime import date, timedelta

from odoo import fields
from odoo.tests.common import TransactionCase


class TestAnalyticsOnHire(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        company = cls.env.company
        cls.customer = cls.env["res.partner"].create({
            "name": "Analytics Customer",
            "is_company": True,
            "customer_type": "company",
            "is_rental_customer": True,
            "company_id": company.id,
        })
        cls.customer_rep = cls.env["res.partner"].create({
            "name": "Analytics Customer Rep",
            "parent_id": cls.customer.id,
        })
        cls.supplier_rep = cls.env["res.partner"].create({
            "name": "Analytics Supplier Rep",
            "parent_id": company.partner_id.id,
        })
        cls.driver = cls.env["res.partner"].create({
            "name": "Analytics Driver",
            "customer_type": "driver",
        })
        cls.truck = cls.env["transport.truck"].create({
            "name": "51A-ANLY",
            "plate": "51A-ANLY",
            "company_id": company.id,
        })
        cls.product_a = cls.env["product.product"].create({
            "name": "Analytics Product A",
            "type": "product",
            "list_price": 1000.0,
        })
        cls.product_b = cls.env["product.product"].create({
            "name": "Analytics Product B",
            "type": "product",
            "list_price": 2000.0,
        })
        cls.project = cls.env["construction.project"].create({
            "name": "Analytics Project",
            "company_id": company.id,
        })
        cls.address = cls.env["construction.address"].create({
            "name": "Analytics Site Address",
            "company_id": company.id,
        })
        cls.work = cls.env["construction.work"].create({
            "name": "Analytics Work Package",
            "project_id": cls.project.id,
            "address_ids": [(6, 0, cls.address.ids)],
            "company_id": company.id,
        })
        cls.contract = cls._create_contract("Analytics Contract")

    @classmethod
    def _create_contract(cls, name):
        contract = cls.env["rental.contract"].create({
            "name": name,
            "a_company_party": cls.customer.id,
            "a_party": cls.customer_rep.id,
            "b_company_party": cls.env.company.partner_id.id,
            "b_party": cls.supplier_rep.id,
            "minimum_rental_months": 0,
            "construction_work_id": cls.work.id,
        })
        cls.env["rental.contract.line"].create({
            "contract_id": contract.id,
            "product_tmpl_id": cls.product_a.product_tmpl_id.id,
            "price_unit": 1000.0,
        })
        cls.env["rental.contract.line"].create({
            "contract_id": contract.id,
            "product_tmpl_id": cls.product_b.product_tmpl_id.id,
            "price_unit": 2000.0,
        })
        contract.status = "active"
        return contract

    def _make_transport(self, transport_type, when, product, qty, state="done"):
        return self.env["rr.transport"].create({
            "rental_contract_id": self.contract.id,
            "type": transport_type,
            "state": state,
            "start_rental_or_return_date": when,
            "driver_id": self.driver.id,
            "transport_truck_id": self.truck.id,
            "vehicle_start_time": when,
            "transport_line_ids": [(0, 0, {
                "product_id": product.id,
                "qty": qty,
            })],
        })

    def test_refresh_and_dashboard_on_hire_widget(self):
        as_of = date(2026, 3, 15)
        self._make_transport("delivery", date(2026, 3, 1), self.product_a, 10)
        self._make_transport("delivery", date(2026, 3, 2), self.product_b, 4)
        self._make_transport("return", date(2026, 3, 10), self.product_a, 3)

        lines = self.env["rental.analytics.on.hire.line"].search_snapshot(
            as_of,
            partner_company_id=self.customer.id,
            force=True,
        )
        self.assertEqual(len(lines), 2)
        by_tmpl = {line.product_tmpl_id.id: line for line in lines}
        line_a = by_tmpl[self.product_a.product_tmpl_id.id]
        line_b = by_tmpl[self.product_b.product_tmpl_id.id]
        self.assertEqual(line_a.physical_qty, 7)
        self.assertEqual(line_b.physical_qty, 4)
        self.assertEqual(line_a.construction_work_id, self.work)
        self.assertEqual(line_a.partner_company_id, self.customer)
        self.assertTrue(line_a.uom_id)
        self.assertTrue(line_a.computed_at)

        data = self.env["rental.analytics.dashboard"].get_dashboard_data({
            "as_of_date": as_of.isoformat(),
            "partner_company_id": self.customer.id,
            "only_active_contracts": True,
            "force_refresh": False,
        })
        self.assertEqual(data["filters"]["as_of_date"], as_of.isoformat())
        widgets = {w["key"]: w for w in data["widgets"]}
        self.assertIn("on_hire_by_product", widgets)
        self.assertIn("receivable_by_partner", widgets)
        widget = widgets["on_hire_by_product"]
        self.assertFalse(widget["total_value"])
        self.assertTrue(widget["totals_by_uom"])
        uom_row = widget["totals_by_uom"][0]
        self.assertEqual(uom_row["physical_qty"], 11)
        self.assertEqual(uom_row["rented_qty"], 11)
        self.assertEqual(uom_row["excess_qty"], 0)
        self.assertEqual(len(widget["chart"]["labels"]), 2)
        self.assertEqual(widget["detail_action"]["res_model"], "rental.analytics.on.hire.line")
        self.assertIn(
            ("as_of_date", "=", as_of),
            widget["detail_action"]["domain"],
        )
        self.assertIn(
            ("partner_company_id", "in", [self.customer.id]),
            widget["detail_action"]["domain"],
        )

    def test_snapshot_ttl_skips_recompute(self):
        as_of = date(2026, 3, 20)
        self._make_transport("delivery", date(2026, 3, 18), self.product_a, 5)
        OnHire = self.env["rental.analytics.on.hire.line"]
        first = OnHire.ensure_snapshot(as_of, force=True)
        computed_at = first[0].computed_at
        second = OnHire.ensure_snapshot(as_of, force=False)
        self.assertEqual(second[0].computed_at, computed_at)
        self.assertEqual(len(second.filtered(
            lambda line: line.partner_company_id == self.customer
        )), 1)

    def test_dashboard_filters_by_construction_work(self):
        as_of = date(2026, 3, 15)
        self._make_transport("delivery", date(2026, 3, 1), self.product_a, 5)
        other_work = self.env["construction.work"].create({
            "name": "Other Work",
            "project_id": self.project.id,
            "address_ids": [(6, 0, self.address.ids)],
            "company_id": self.env.company.id,
        })
        data = self.env["rental.analytics.dashboard"].get_dashboard_data({
            "as_of_date": as_of.isoformat(),
            "construction_work_id": other_work.id,
            "only_active_contracts": True,
            "force_refresh": True,
        })
        on_hire = next(
            w for w in data["widgets"] if w["key"] == "on_hire_by_product"
        )
        self.assertFalse(on_hire["totals_by_uom"])
        self.assertFalse(on_hire["chart"]["labels"])

    def test_dashboard_filters_multi_partner_and_work(self):
        as_of = date(2026, 3, 15)
        self._make_transport("delivery", date(2026, 3, 1), self.product_a, 5)
        other_customer = self.env["res.partner"].create({
            "name": "Other Renter Co",
            "is_company": True,
            "customer_type": "company",
            "is_rental_customer": True,
            "company_id": self.env.company.id,
        })
        other_work = self.env["construction.work"].create({
            "name": "Other Work Multi",
            "project_id": self.project.id,
            "address_ids": [(6, 0, self.address.ids)],
            "company_id": self.env.company.id,
        })
        data = self.env["rental.analytics.dashboard"].get_dashboard_data({
            "as_of_date": as_of.isoformat(),
            "partner_company_ids": [self.customer.id, other_customer.id],
            "construction_work_ids": [self.work.id, other_work.id],
            "only_active_contracts": True,
            "force_refresh": True,
        })
        self.assertEqual(
            set(data["filters"]["partner_company_ids"]),
            {self.customer.id, other_customer.id},
        )
        on_hire = next(
            w for w in data["widgets"] if w["key"] == "on_hire_by_product"
        )
        self.assertTrue(on_hire["totals_by_uom"])
        self.assertIn(
            ("partner_company_id", "in", [self.customer.id, other_customer.id]),
            on_hire["detail_action"]["domain"],
        )
        self.assertIn(
            ("construction_work_id", "in", [self.work.id, other_work.id]),
            on_hire["detail_action"]["domain"],
        )

    def test_cron_cleanup_old_snapshots(self):
        OnHire = self.env["rental.analytics.on.hire.line"]
        old_date = fields.Date.context_today(OnHire) - timedelta(days=30)
        OnHire.create({
            "company_id": self.env.company.id,
            "as_of_date": old_date,
            "computed_at": fields.Datetime.now(),
            "partner_company_id": self.customer.id,
            "rental_contract_id": self.contract.id,
            "product_tmpl_id": self.product_a.product_tmpl_id.id,
            "uom_id": self.product_a.uom_id.id,
            "uom_name": self.product_a.uom_id.name,
            "rented_qty": 1,
            "excess_qty": 0,
            "physical_qty": 1,
        })
        OnHire._cron_cleanup_old_snapshots()
        self.assertFalse(OnHire.search([("as_of_date", "=", old_date)]))

    def test_action_open_on_hire_detail_refreshes_today(self):
        OnHire = self.env["rental.analytics.on.hire.line"]
        today = fields.Date.context_today(OnHire)
        self._make_transport("delivery", today, self.product_a, 2)
        action = OnHire.action_open_on_hire_detail()
        self.assertEqual(action["res_model"], "rental.analytics.on.hire.line")
        self.assertIn(("as_of_date", "=", today), action["domain"])
