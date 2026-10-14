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

    def test_duplicate_transport_creates_draft_copy_with_lines(self):
        when = date(2026, 6, 10)
        transport = self.env["rr.transport"].create({
            "rental_contract_id": self._contract.id,
            "type": "delivery",
            "state": "done",
            "start_rental_or_return_date": when,
            "driver_id": self._driver.id,
            "transport_truck_id": self._truck.id,
            "vehicle_start_time": when,
            "fee": 500,
            "fee_actual": 450,
            "fee_billed_date": date(2026, 6, 30),
            "vehicle_arrival_time": "2026-06-10 10:00:00",
            "transport_line_ids": [(0, 0, {
                "product_id": self._product.id,
                "qty": 7,
                "non_billable_qty": 2,
            })],
        })
        transport.external_invoice_code = "HD-001"
        action = transport.action_duplicate_transport()
        new = self.env["rr.transport"].browse(action["res_id"])
        self.assertEqual(action["target"], "current")
        self.assertFalse(new.external_invoice_code)
        self.assertNotEqual(new, transport)
        self.assertNotEqual(new.code, transport.code)
        self.assertEqual(new.state, "draft")
        self.assertEqual(new.fee, 500)
        self.assertEqual(new.fee_actual, 0)
        self.assertFalse(new.fee_billed_date)
        self.assertFalse(new.vehicle_arrival_time)
        self.assertEqual(new.rental_contract_id, transport.rental_contract_id)
        self.assertEqual(new.start_rental_or_return_date, when)
        self.assertFalse(new.picking_ids)
        self.assertEqual(len(new.transport_line_ids), 1)
        self.assertEqual(new.transport_line_ids.product_id, self._product)
        self.assertEqual(new.transport_line_ids.qty, 7)
        self.assertEqual(new.transport_line_ids.non_billable_qty, 2)
        self.assertEqual(transport.state, "done")
        self.assertEqual(len(transport.transport_line_ids), 1)

    def test_duplicate_transport_from_contract_tab_keeps_compensation(self):
        when = date(2026, 6, 11)
        transport = self.env["rr.transport"].create({
            "rental_contract_id": self._contract.id,
            "type": "compensation",
            "state": "cancel",
            "start_rental_or_return_date": when,
            "driver_id": self._driver.id,
            "transport_truck_id": self._truck.id,
            "vehicle_start_time": when,
            "transport_line_ids": [(0, 0, {
                "product_id": self._product.id,
                "qty": 4,
                "damage_ratio": "50",
                "fine_amount": 123.0,
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
        })
        self._contract.write({"status": "active"})
        action = transport.with_context(rr_transport_from_contract=True).action_duplicate_transport()
        self.assertEqual(action["tag"], "display_notification")
        reload_action = action["params"]["next"]
        self.assertEqual(reload_action["tag"], "rental_reload_and_open")
        open_action = reload_action["params"]["next"]
        self.assertEqual(open_action["target"], "new")
        self.assertTrue(open_action["context"]["rr_transport_from_contract"])
        new = self.env["rr.transport"].search(
            [("rental_contract_id", "=", transport.rental_contract_id.id), ("id", "!=", transport.id)]
        )
        self.assertEqual(len(new), 1)
        self.assertEqual(open_action["res_id"], new.id)
        self.assertEqual(new.state, "draft")
        self.assertEqual(new.type, "compensation")
        self.assertFalse(new.picking_ids)
        self.assertEqual(len(transport.picking_ids), 1)
        self.assertEqual(new.transport_line_ids.damage_ratio, "50")
        self.assertEqual(new.transport_line_ids.fine_amount, 123.0)
        self.assertEqual(new.transport_line_ids.transport_id, new)

    # --- Hoàn thành: tạo phiếu kho + xác nhận một bước -------------------------

    def _make_transport(self, qty, ttype="delivery", **line_vals):
        when = date(2026, 6, 12)
        return self.env["rr.transport"].create({
            "rental_contract_id": self._contract.id,
            "type": ttype,
            "state": "draft",
            "start_rental_or_return_date": when,
            "driver_id": self._driver.id,
            "transport_truck_id": self._truck.id,
            "vehicle_start_time": when,
            "transport_line_ids": [(0, 0, dict({"product_id": self._product.id, "qty": qty}, **line_vals))],
        })

    def _set_stock(self, transport, qty):
        transport._rental_prepare_picking_type_and_locations()
        self.env["stock.quant"]._update_available_quantity(self._product, transport.location_id, qty)

    def test_complete_with_enough_stock_validates_picking(self):
        transport = self._make_transport(3)
        self._set_stock(transport, 10)
        action = transport.action_complete_transport()
        self.assertEqual(action["tag"], "display_notification")
        self.assertEqual(transport.state, "done")
        self.assertEqual(len(transport.picking_ids), 1)
        self.assertEqual(transport.picking_ids.state, "done")

    def test_complete_shortage_opens_wizard_then_allows_negative(self):
        transport = self._make_transport(5)
        self._set_stock(transport, 2)
        src = transport.location_id
        action = transport.with_context(rr_transport_from_contract=True).action_complete_transport()
        self.assertEqual(action["res_model"], "rr.transport.complete.wizard")
        self.assertEqual(transport.state, "draft")
        self.assertFalse(transport.picking_ids)
        wizard = self.env["rr.transport.complete.wizard"].browse(action["res_id"])
        self.assertIn(self._product.display_name, wizard.message)
        self.assertIn("<td class='text-end'>5</td>", wizard.message)
        self.assertNotIn("size_class", action["context"])
        result = wizard.with_context(action["context"]).action_confirm()
        self.assertEqual(result["params"]["next"]["tag"], "rental_reload_and_open")
        self.assertEqual(transport.state, "done")
        self.assertEqual(transport.picking_ids.state, "done")
        self.assertEqual(self._product.with_context(location=src.id).qty_available, -3)

    def test_complete_return_does_not_warn(self):
        transport = self._make_transport(4, ttype="return")
        action = transport.action_complete_transport()
        self.assertNotEqual(action.get("res_model"), "rr.transport.complete.wizard")
        self.assertEqual(transport.state, "done")
        self.assertEqual(transport.picking_ids.state, "done")

    def test_complete_compensation_full_damage_closes_without_picking(self):
        transport = self._make_transport(2, ttype="compensation", damage_ratio="100")
        transport.action_complete_transport()
        self.assertEqual(transport.state, "done")
        self.assertFalse(transport.picking_ids)

    def test_complete_rejects_non_draft(self):
        transport = self._make_transport(1)
        transport.state = "cancel"
        with self.assertRaises(UserError):
            transport.action_complete_transport()

    def test_complete_blocked_when_open_picking_exists(self):
        transport = self._make_transport(3)
        self._set_stock(transport, 10)
        picking = transport._rental_create_picking()
        with self.assertRaises(UserError) as err:
            transport.action_complete_transport()
        self.assertIn(picking.name, str(err.exception))
        self.assertEqual(transport.state, "draft")
        self.assertNotEqual(picking.state, "done")

    def test_complete_sums_lines_of_same_product_for_shortage(self):
        transport = self._make_transport(3)
        transport.write({"transport_line_ids": [(0, 0, {"product_id": self._product.id, "qty": 3})]})
        self._set_stock(transport, 4)
        action = transport.action_complete_transport()
        self.assertEqual(action["res_model"], "rr.transport.complete.wizard")

    def test_complete_requires_lines(self):
        transport = self._make_transport(1, ttype="compensation", damage_ratio="100")
        transport.transport_line_ids.unlink()
        with self.assertRaises(UserError):
            transport.action_complete_transport()
        self.assertEqual(transport.state, "draft")

    def test_cancelled_shortage_wizard_leaves_transport_draft(self):
        transport = self._make_transport(5)
        self._set_stock(transport, 1)
        action = transport.action_complete_transport()
        self.assertEqual(action["res_model"], "rr.transport.complete.wizard")
        # NV bấm Hủy: không gọi action_confirm.
        self.assertEqual(transport.state, "draft")
        self.assertFalse(transport.picking_ids)

    def test_line_display_name_falls_back_to_transport_and_product(self):
        transport = self._make_transport(2)
        line = transport.transport_line_ids
        self.assertFalse(line.name)
        self.assertEqual(line.display_name, "%s - %s" % (transport.code, self._product.display_name))

    def test_create_transport_from_contract_tracks_existing_lines(self):
        """Lưu HĐ khi tạo phiếu mới (dialog tab HĐ) không crash tracking rr_transport_line_ids."""
        old = self._make_transport(2)
        old_lines = self._contract.rr_transport_line_ids
        new = self._make_transport(1)
        col_info = self._contract.fields_get(["rr_transport_line_ids"])["rr_transport_line_ids"]
        vals = self.env["mail.tracking.value"]._create_tracking_values(
            old_lines, self._contract.rr_transport_line_ids, "rr_transport_line_ids", col_info, self._contract,
        )
        self.assertIn(old.code, vals["old_value_char"])
        self.assertIn(new.code, vals["new_value_char"])
