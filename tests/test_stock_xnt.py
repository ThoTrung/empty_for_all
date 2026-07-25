# -*- coding: utf-8 -*-
from datetime import date, datetime, timedelta

from odoo.tests.common import TransactionCase

from odoo.addons.rental.services import rental_stock_xnt as stock_xnt


class TestStockXnt(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.warehouse = cls.env["stock.warehouse"].search(
            [("company_id", "=", cls.company.id)], limit=1
        )
        if not cls.warehouse:
            raise AssertionError("Need a warehouse for stock XNT tests")
        cls.stock_loc = cls.warehouse.lot_stock_id
        cls.supplier_loc = cls.env.ref("stock.stock_location_suppliers")
        cls.customer_loc = cls.env.ref("stock.stock_location_customers")
        cls.product = cls.env["product.product"].create({
            "name": "XNT Storable Product",
            "type": "product",
            "list_price": 100.0,
        })
        cls.product_b = cls.env["product.product"].create({
            "name": "XNT Other Product",
            "type": "product",
            "list_price": 50.0,
        })

    def _done_move(self, product, qty, src, dest, when, picking_type=None):
        """Create and complete a stock.move at ``when`` (date or datetime)."""
        from datetime import time as time_cls
        if isinstance(when, date) and not isinstance(when, datetime):
            when_dt = datetime.combine(when, time_cls(12, 0, 0))
        else:
            when_dt = when
        Move = self.env["stock.move"]
        vals = {
            "name": product.display_name,
            "product_id": product.id,
            "product_uom": product.uom_id.id,
            "product_uom_qty": qty,
            "location_id": src.id,
            "location_dest_id": dest.id,
            "company_id": self.company.id,
            "date": when_dt,
        }
        if picking_type:
            vals["picking_type_id"] = picking_type.id
        move = Move.create(vals)
        move._action_confirm()
        move.quantity = qty
        move.picked = True
        move._action_done()
        # `_action_done` stamps date=now — restore historical date for report tests.
        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE stock_move SET date = %s WHERE id = %s",
            (when_dt, move.id),
        )
        if move.move_line_ids:
            self.env.cr.execute(
                "UPDATE stock_move_line SET date = %s WHERE move_id = %s",
                (when_dt, move.id),
            )
        self.env.invalidate_all()
        return move

    def test_onhand_and_xnt_period(self):
        # Opening: receive 100 before period
        self._done_move(
            self.product, 100, self.supplier_loc, self.stock_loc, date(2026, 1, 10)
        )
        # Period: receive 20 (PO-like), deliver 30 (SO-like), deliver 10 (rental-like)
        self._done_move(
            self.product, 20, self.supplier_loc, self.stock_loc, date(2026, 2, 5)
        )
        self._done_move(
            self.product, 30, self.stock_loc, self.customer_loc, date(2026, 2, 10)
        )
        self._done_move(
            self.product, 10, self.stock_loc, self.customer_loc, date(2026, 2, 15)
        )

        onhand = stock_xnt.calc_stock_on_hand_as_of(
            self.env,
            date(2026, 2, 28),
            company_ids=[self.company.id],
        )
        by_product = {row["product_id"]: row for row in onhand}
        self.assertIn(self.product.id, by_product)
        self.assertAlmostEqual(by_product[self.product.id]["qty_on_hand"], 80.0)

        xnt = stock_xnt.calc_xnt_lines(
            self.env,
            date(2026, 2, 1),
            date(2026, 2, 28),
            company_ids=[self.company.id],
            product_ids=[self.product.id],
        )
        self.assertEqual(len(xnt), 1)
        line = xnt[0]
        self.assertAlmostEqual(line["opening_qty"], 100.0)
        self.assertAlmostEqual(line["in_qty"], 20.0)
        self.assertAlmostEqual(line["out_qty"], 40.0)
        self.assertAlmostEqual(line["closing_qty"], 80.0)
        self.assertAlmostEqual(
            line["closing_qty"],
            line["opening_qty"] + line["in_qty"] - line["out_qty"],
        )

    def test_internal_transfer_ignored(self):
        self._done_move(
            self.product, 50, self.supplier_loc, self.stock_loc, date(2026, 3, 1)
        )
        internal_other = self.env["stock.location"].search([
            ("usage", "=", "internal"),
            ("id", "!=", self.stock_loc.id),
            ("id", "child_of", self.warehouse.view_location_id.id),
        ], limit=1)
        if not internal_other:
            internal_other = self.env["stock.location"].create({
                "name": "XNT Extra Stock",
                "usage": "internal",
                "location_id": self.warehouse.view_location_id.id,
                "company_id": self.company.id,
            })
        self._done_move(
            self.product, 15, self.stock_loc, internal_other, date(2026, 3, 10)
        )
        xnt = stock_xnt.calc_xnt_lines(
            self.env,
            date(2026, 3, 1),
            date(2026, 3, 31),
            company_ids=[self.company.id],
            warehouse_ids=[self.warehouse.id],
            product_ids=[self.product.id],
        )
        self.assertEqual(len(xnt), 1)
        self.assertAlmostEqual(xnt[0]["in_qty"], 50.0)
        self.assertAlmostEqual(xnt[0]["out_qty"], 0.0)
        self.assertAlmostEqual(xnt[0]["closing_qty"], 50.0)

    def test_dashboard_widget_and_xnt_summary(self):
        self._done_move(
            self.product, 40, self.supplier_loc, self.stock_loc, date(2026, 4, 1)
        )
        self._done_move(
            self.product, 5, self.stock_loc, self.customer_loc, date(2026, 4, 12)
        )
        Dash = self.env["rental.analytics.dashboard"]
        data = Dash.get_dashboard_data({
            "as_of_date": "2026-04-15",
            "force_refresh": True,
        })
        keys = {w["key"] for w in data["widgets"]}
        self.assertIn("warehouse_stock", keys)
        stock_widget = next(w for w in data["widgets"] if w["key"] == "warehouse_stock")
        self.assertTrue(stock_widget.get("detail_action"))

        onhand_lines = self.env["rental.analytics.stock.onhand.line"].search([
            ("as_of_date", "=", date(2026, 4, 15)),
            ("product_id", "=", self.product.id),
        ])
        self.assertEqual(len(onhand_lines), 1)
        self.assertAlmostEqual(onhand_lines.qty_on_hand, 35.0)

        summary = Dash.get_xnt_summary({
            "date_from": "2026-04-01",
            "date_to": "2026-04-30",
            "as_of_date": "2026-04-15",
        })
        self.assertEqual(len(summary["chart"]["datasets"]), 2)
        self.assertGreaterEqual(summary["line_count"], 1)

        action = Dash.action_open_xnt_wizard({
            "date_from": "2026-04-01",
            "date_to": "2026-04-30",
        })
        self.assertEqual(action["res_model"], "rental.stock.xnt.wizard")
        wizard = self.env["rental.stock.xnt.wizard"].browse(action["res_id"])
        self.assertTrue(wizard.line_ids)
        line = wizard.line_ids.filtered(lambda l: l.product_id == self.product)
        self.assertTrue(line)
        self.assertAlmostEqual(line.closing_qty, 35.0)

    def test_onhand_snapshot_model(self):
        self._done_move(
            self.product_b, 12, self.supplier_loc, self.stock_loc, date(2026, 5, 1)
        )
        lines = self.env["rental.analytics.stock.onhand.line"].ensure_snapshot(
            date(2026, 5, 2),
            force=True,
        )
        match = lines.filtered(lambda l: l.product_id == self.product_b)
        self.assertEqual(len(match), 1)
        self.assertAlmostEqual(match.qty_on_hand, 12.0)
