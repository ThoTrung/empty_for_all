# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class RentalProductTemplateSet(models.Model):
    _name = "rental.product.template.set"
    _description = "Mẫu sản phẩm hợp đồng"
    _inherit = ["mc.group.mixin"]
    _order = "name, id"

    name = fields.Char(string="Tên mẫu", required=True, tracking=True)
    active = fields.Boolean(default=True)
    line_ids = fields.One2many(
        "rental.product.template.set.line",
        "template_set_id",
        string="Dòng sản phẩm",
        copy=True,
    )
    product_count = fields.Integer(
        string="Số sản phẩm",
        compute="_compute_product_count",
        store=False,
    )

    @api.depends("line_ids")
    def _compute_product_count(self):
        for rec in self:
            rec.product_count = len(rec.line_ids)

    @api.constrains("line_ids")
    def _check_line_ids(self):
        for rec in self:
            if not rec.line_ids:
                raise ValidationError(_("Bạn phải chọn ít nhất một sản phẩm cho mẫu."))


class RentalProductTemplateSetLine(models.Model):
    _name = "rental.product.template.set.line"
    _description = "Dòng sản phẩm của mẫu hợp đồng"
    _order = "sequence, id"

    sequence = fields.Integer(default=10)
    template_set_id = fields.Many2one(
        "rental.product.template.set",
        string="Mẫu sản phẩm hợp đồng",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(
        related="template_set_id.company_id",
        store=True,
        readonly=True,
        index=True,
    )
    currency_id = fields.Many2one(
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )

    product_tmpl_id = fields.Many2one(
        "product.template",
        string="Sản phẩm",
        required=True,
        domain=[("sale_ok", "=", True), ("active", "=", True)],
        options={"no_create": True, "no_create_edit": True},
    )
    name = fields.Text(string="Mô tả")
    product_uom_qty = fields.Integer(string="Số lượng", default=1)
    price_unit = fields.Float(string="Giá thuê", required=True, default=0)
    standard_price = fields.Float(string="Giá vốn")
    compensation_price = fields.Float(string="Giá đền bù")
    uom_id = fields.Many2one("uom.uom", string="Đơn vị tính")

    @api.onchange("product_tmpl_id")
    def _onchange_product_tmpl_id(self):
        for line in self:
            pt = line.product_tmpl_id
            if not pt:
                continue
            line.name = getattr(pt, "get_product_multiline_description_sale", lambda: pt.display_name)()
            line.price_unit = pt.list_price or 0.0
            line.standard_price = pt.standard_price or 0.0
            line.compensation_price = pt.compensation_price or 0.0
            line.uom_id = pt.uom_id or False
