# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.exceptions import UserError


class StockLocation(models.Model):
    _inherit = "stock.location"

    is_rental_subrent_stock = fields.Boolean(
        string="Kho thuê ngoài",
        default=False,
        index=True,
        help="Location nội bộ chứa hàng thuê từ NCC (tách khỏi kho tự có).",
    )


class StockWarehouse(models.Model):
    _inherit = "stock.warehouse"

    def _rental_subrent_get_or_create_location(self):
        """Internal location WH/Subrent for into_stock flow (per warehouse)."""
        self.ensure_one()
        Location = self.env["stock.location"].sudo()
        existing = Location.search([
            ("is_rental_subrent_stock", "=", True),
            ("company_id", "=", self.company_id.id),
            ("usage", "=", "internal"),
            ("location_id", "child_of", self.view_location_id.id),
        ], limit=1)
        if existing:
            return existing
        if not self.view_location_id:
            raise UserError(_("Kho %(wh)s chưa có view location.") % {"wh": self.display_name})
        return Location.create({
            "name": _("Kho thuê ngoài"),
            "usage": "internal",
            "location_id": self.lot_stock_id.location_id.id
            if self.lot_stock_id and self.lot_stock_id.location_id
            else self.view_location_id.id,
            "company_id": self.company_id.id,
            "is_rental_subrent_stock": True,
        })


class ResCompany(models.Model):
    _inherit = "res.company"

    def _rental_subrent_stock_location(self):
        self.ensure_one()
        Location = self.env["stock.location"].sudo()
        loc = Location.search([
            ("is_rental_subrent_stock", "=", True),
            ("company_id", "=", self.id),
            ("usage", "=", "internal"),
        ], limit=1)
        if loc:
            return loc
        wh = self.env["stock.warehouse"].sudo().search(
            [("company_id", "=", self.id)], limit=1
        )
        if not wh:
            raise UserError(_("Công ty %(c)s chưa có kho.") % {"c": self.display_name})
        return wh._rental_subrent_get_or_create_location()

    def _rental_subrent_supplier_location(self):
        self.ensure_one()
        try:
            return self.env.ref("stock.stock_location_suppliers")
        except ValueError as exc:
            raise UserError(_("Không tìm thấy location Nhà cung cấp chuẩn.")) from exc
