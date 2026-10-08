# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class RentalSubrentReceipt(models.Model):
    _name = "rental.subrent.receipt"
    _description = "Phiếu nhận hàng từ NCC"
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
        domain="[('state', '=', 'active')]",
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
        string="Ngày nhận",
        required=True,
        default=fields.Date.context_today,
        tracking=True,
    )
    stock_flow = fields.Selection(
        [
            ("into_stock", "Về kho"),
            ("pass_through", "Chuẩn bị giao thẳng (tạo lô)"),
        ],
        default="into_stock",
        required=True,
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
        "rental.subrent.receipt.line",
        "receipt_id",
        string="Dòng",
        copy=True,
    )
    picking_ids = fields.Many2many(
        "stock.picking",
        string="Phiếu kho",
        copy=False,
    )
    lot_ids = fields.One2many(
        "rental.subrent.lot",
        "receipt_id",
        string="Lô tạo ra",
    )
    note = fields.Text(string="Ghi chú")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("New")) in (False, _("New"), "New"):
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code("rental.subrent.receipt")
                    or _("TN/NH")
                )
        return super().create(vals_list)

    def action_confirm(self):
        for rec in self:
            if rec.state != "draft":
                raise UserError(_("Chỉ xác nhận phiếu nháp."))
            if not rec.line_ids:
                raise UserError(_("Thêm ít nhất một dòng."))
            if rec.subrent_contract_id.state != "active":
                raise UserError(_("HĐ thuê ngoài phải đang hiệu lực."))
            policy = rec.subrent_contract_id.get_subrent_policy()
            policy.on_receipt_confirm(rec)
            rec.state = "done"
        return True

    def action_cancel(self):
        for rec in self:
            if rec.state != "done":
                rec.state = "cancel"
                continue
            raise UserError(
                _("Không hủy phiếu đã hoàn thành từ đây — trả NCC / đảo thủ công nếu cần.")
            )
        return True

    def _contract_line_for_product(self, product):
        self.ensure_one()
        line = self.subrent_contract_id.line_ids.filtered(
            lambda l: l.product_tmpl_id == product.product_tmpl_id
        )[:1]
        if not line:
            raise ValidationError(
                _("Sản phẩm %(p)s không có trên HĐ %(c)s.")
                % {"p": product.display_name, "c": self.subrent_contract_id.name}
            )
        return line


class RentalSubrentReceiptLine(models.Model):
    _name = "rental.subrent.receipt.line"
    _description = "Dòng phiếu nhận NCC"
    _order = "id"

    receipt_id = fields.Many2one(
        "rental.subrent.receipt",
        required=True,
        ondelete="cascade",
        index=True,
    )
    product_id = fields.Many2one("product.product", string="Sản phẩm", required=True)
    qty = fields.Float(string="Số lượng", required=True, default=1.0)
    lot_id = fields.Many2one("rental.subrent.lot", string="Lô", readonly=True, copy=False)
