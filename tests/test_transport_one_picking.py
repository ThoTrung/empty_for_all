# -*- coding: utf-8 -*-
from datetime import date

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestTransportOnePicking(TransactionCase):
    """Temporary rule: at most one non-cancel stock.picking per rr.transport."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        company = cls.env.company
        cls._a_company = cls.env["res.partner"].create({
            "name": "One Picking Renter",
            "is_company": True,
            "customer_type": "company",
            "is_rental_customer": True,
        })
        cls._a_party = cls.env["res.partner"].create({
            "name": "One Picking A rep",
            "parent_id": cls._a_company.id,
        })
        cls._b_party = cls.env["res.partner"].create({
            "name": "One Picking B rep",
            "parent_id": company.partner_id.id,
        })
        cls._driver = cls.env["res.partner"].create({
            "name": "One Picking Driver",
            "customer_type": "driver",
        })
        cls._truck = cls.env["transport.truck"].create({
            "plate": "29H-92001",
            "name": "29H-92001",
            "company_id": company.id,
        })
        cls._product = cls.env["product.product"].create({
            "name": "Khóa giáo one-picking",
            "type": "product",
        })
        cls._contract = cls.env["rental.contract"].create({
            "a_company_party": cls._a_company.id,
            "a_party": cls._a_party.id,
            "b_company_party": company.partner_id.id,
            "b_party": cls._b_party.id,
        })
        cls.env["rental.contract.line"].create({
            "contract_id": cls._contract.id,
            "product_tmpl_id": cls._product.product_tmpl_id.id,
            "price_unit": 100.0,
        })
        picking_type = cls.env["stock.picking.type"].search([
            ("code", "=", "outgoing"),
            ("company_id", "=", company.id),
        ], limit=1)
        if not picking_type:
            picking_type = cls.env["stock.picking.type"].search([
                ("code", "=", "outgoing"),
            ], limit=1)
        cls._picking_type = picking_type

    def test_create_pickings_raises_when_non_cancel_picking_exists(self):
        self.assertTrue(self._picking_type, "Need an outgoing picking type for the test")
        when = date(2026, 6, 10)
        transport = self.env["rr.transport"].create({
            "rental_contract_id": self._contract.id,
            "type": "delivery",
            "state": "draft",
            "start_rental_or_return_date": when,
            "driver_id": self._driver.id,
            "transport_truck_id": self._truck.id,
            "vehicle_start_time": when,
            "plate": "29H-92001",
            "transport_line_ids": [(0, 0, {
                "product_id": self._product.id,
                "qty": 3,
            })],
        })
        self.env["stock.picking"].create({
            "picking_type_id": self._picking_type.id,
            "location_id": self._picking_type.default_location_src_id.id
            or self.env.ref("stock.stock_location_stock").id,
            "location_dest_id": self._picking_type.default_location_dest_id.id
            or self.env.ref("stock.stock_location_customers").id,
            "company_id": self.env.company.id,
            "rental_transport_id": transport.id,
            "origin": transport.code or "test",
        })
        with self.assertRaises(UserError) as err:
            transport.action_create_pickings()
        msg = str(err.exception)
        self.assertTrue(
            "chưa xác nhận" in msg or "đã có phiếu kho" in msg,
            msg,
        )
