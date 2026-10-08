# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


LEDGER_MOVE_TYPES = [
    ("receive", "Nhận từ NCC"),
    ("deliver_customer", "Giao khách"),
    ("return_customer", "Khách trả"),
    ("return_supplier", "Trả NCC"),
    ("damage", "Hỏng / đền bù"),
    ("cancel_reversal", "Đảo khi hủy VC"),
]


class RentalSubrentLedger(models.Model):
    _name = "rental.subrent.ledger"
    _description = "Sổ cái chuyển động thuê ngoài"
    _order = "date asc, id asc"
    _rec_name = "display_name"

    lot_id = fields.Many2one(
        "rental.subrent.lot",
        string="Lô",
        required=True,
        ondelete="restrict",
        index=True,
    )
    company_id = fields.Many2one(
        related="lot_id.company_id",
        store=True,
        readonly=True,
        index=True,
    )
    move_type = fields.Selection(LEDGER_MOVE_TYPES, required=True, index=True)
    qty = fields.Float(string="Số lượng", required=True, digits="Product Unit of Measure")
    date = fields.Date(string="Ngày", required=True, index=True, default=fields.Date.context_today)
    product_id = fields.Many2one(related="lot_id.product_id", store=True, readonly=True)
    receipt_id = fields.Many2one("rental.subrent.receipt", ondelete="set null", index=True)
    return_id = fields.Many2one("rental.subrent.return", ondelete="set null", index=True)
    transport_id = fields.Many2one("rr.transport", ondelete="set null", index=True)
    transport_line_id = fields.Many2one("rr.transport.line", ondelete="set null", index=True)
    note = fields.Char(string="Ghi chú")
    display_name = fields.Char(compute="_compute_display_name")

    @api.depends("lot_id", "move_type", "qty", "date")
    def _compute_display_name(self):
        type_map = dict(LEDGER_MOVE_TYPES)
        for rec in self:
            rec.display_name = "%s %s × %s (%s)" % (
                rec.date or "",
                type_map.get(rec.move_type, rec.move_type),
                rec.qty,
                rec.lot_id.name or "",
            )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records.mapped("lot_id")._recompute_qty_fields()
        return records

    def write(self, vals):
        raise UserError(_("Sổ cái thuê ngoài là bất biến — không sửa dòng đã ghi."))

    def unlink(self):
        if self.env.context.get("rental_subrent_allow_ledger_unlink"):
            lots = self.mapped("lot_id")
            res = super().unlink()
            lots._recompute_qty_fields()
            return res
        raise UserError(_("Sổ cái thuê ngoài là bất biến — không xóa dòng đã ghi."))
