# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class RentalSubrentReturn(models.Model):
    _name = "rental.subrent.return"
    _description = "Phiếu trả hàng NCC"
    _inherit = ["mc.group.mixin", "mail.thread", "mail.activity.mixin"]
    _order = "date desc, id desc"
    _rec_name = "name"

    name = fields.Char(
        string="Mã phiếu",
        required=True,
        copy=False,
        default=lambda self: _("New"),
        tracking=True,
    )
    subrent_contract_id = fields.Many2one(
        "rental.subrent.contract",
        string="HĐ thuê ngoài",
        required=True,
        domain="[('state', 'in', ('active', 'done'))]",
        tracking=True,
        index=True,
    )
    policy_code = fields.Selection(
        related="subrent_contract_id.policy_code",
        store=True,
        readonly=True,
    )
    supplier_id = fields.Many2one(
        related="subrent_contract_id.supplier_id",
        store=True,
        readonly=True,
    )
    date = fields.Date(
        string="Ngày trả",
        required=True,
        default=fields.Date.context_today,
        tracking=True,
    )
    state = fields.Selection(
        [
            ("draft", "Nháp"),
            ("done", "Hoàn thành"),
            ("cancel", "Hủy"),
        ],
        default="draft",
        required=True,
        tracking=True,
        index=True,
    )
    line_ids = fields.One2many(
        "rental.subrent.return.line",
        "return_id",
        string="Dòng",
        copy=True,
    )
    picking_ids = fields.Many2many("stock.picking", string="Phiếu kho", copy=False)
    note = fields.Text(string="Ghi chú")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("New")) in (False, _("New"), "New"):
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code("rental.subrent.return")
                    or _("TN/TR")
                )
        return super().create(vals_list)

    def action_confirm(self):
        for rec in self:
            if rec.state != "draft":
                raise UserError(_("Chỉ xác nhận phiếu nháp."))
            if not rec.line_ids:
                raise UserError(_("Thêm ít nhất một dòng."))
            policy = rec.subrent_contract_id.get_subrent_policy()
            policy.on_return_confirm(rec)
            rec.state = "done"
        return True


class RentalSubrentReturnLine(models.Model):
    _name = "rental.subrent.return.line"
    _description = "Dòng phiếu trả NCC"
    _order = "id"

    return_id = fields.Many2one(
        "rental.subrent.return",
        required=True,
        ondelete="cascade",
        index=True,
    )
    policy_code = fields.Selection(
        related="return_id.policy_code",
        readonly=True,
    )
    lot_id = fields.Many2one(
        "rental.subrent.lot",
        string="Lô",
        ondelete="restrict",
        domain="[('state', '!=', 'closed'), ('qty_at_subrent_wh', '>', 0)]",
    )
    product_id = fields.Many2one(
        "product.product",
        string="Sản phẩm",
        required=True,
    )
    qty = fields.Float(string="Số lượng", required=True, default=1.0)

    @api.model_create_multi
    def create(self, vals_list):
        Lot = self.env["rental.subrent.lot"]
        for vals in vals_list:
            if vals.get("lot_id") and not vals.get("product_id"):
                vals["product_id"] = Lot.browse(vals["lot_id"]).product_id.id
        return super().create(vals_list)

    @api.onchange("lot_id")
    def _onchange_lot_id(self):
        if self.lot_id:
            self.product_id = self.lot_id.product_id
