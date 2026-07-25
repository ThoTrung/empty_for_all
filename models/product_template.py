# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class ProductTemplate(models.Model):
    _inherit = "product.template"
    _order = "order, id"

    detailed_type = fields.Selection(default="product")

    compensation_price = fields.Float(
        string="Giá đền bù",
        # company_dependent=True,  # separate value per company
        tracking=True,
    )
    rental_price_day = fields.Float(
        string="Giá thuê theo ngày (mẫu)",
        digits="Product Price",
        tracking=True,
        help="Giá thuê một ngày trên mẫu sản phẩm. Biến thể được quy đổi theo tỷ lệ Giá bán/Giá mẫu.",
    )

    use_variant_multiplier = fields.Boolean(
        string="Dùng hệ số giá biến thể",
        default=True,
        help="Nếu bật, giá biến thể = giá mẫu × hệ số từ giá trị thuộc tính."
    )

    company_id = fields.Many2one(
        'res.company',
        required=True,  # force per-company product
        default=lambda self: self.env.company,  # default current company
        index=True,
        ondelete='restrict',
    )

    order = fields.Integer(
        string="Thứ tự",
        default=10,
        help="Thứ tự cột khi xuất biểu mẫu bảng khối lượng (import Excel).",
    )

    def _recompute_variant_extras_from_multipliers(self):
        """Set each PTAV.price_extra = base_price * (multiplier - 1)."""
        for rec in self:
            if not rec.use_variant_multiplier:
                continue
            base = rec.list_price or 0.0
            for ali in rec.attribute_line_ids:
                for v in ali.product_template_value_ids:
                    mult = v.price_multiplier or 1.0
                    v.price_extra = base * (mult - 1)

    def _rental_sync_variant_daily_prices(self):
        """Cập nhật giá/ngày trên từng biến thể khi đổi giá/ngày hoặc list_price mẫu."""
        for tmpl in self:
            tmpl.product_variant_ids._rental_apply_daily_from_template()

    def write(self, vals):
        res = super().write(vals)
        # Recompute when base price or toggle changes, or when attribute lines change
        if any(k in vals for k in ("list_price", "use_variant_multiplier", "attribute_line_ids")):
            self._recompute_variant_extras_from_multipliers()
        if any(
            k in vals
            for k in ("rental_price_day", "list_price", "use_variant_multiplier", "attribute_line_ids")
        ):
            self._rental_sync_variant_daily_prices()
        return res

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._recompute_variant_extras_from_multipliers()
        records._rental_sync_variant_daily_prices()
        return records


class ProductTemplateAttributeValue(models.Model):
    _inherit = "product.template.attribute.value"

    # New field used as multiplier instead of default price_extra
    price_multiplier = fields.Float(
        string="Hệ số giá",
        default=1.0,
        help="Giá biến thể = giá mẫu × hệ số này.\n"
             "price_extra bên dưới sẽ được cập nhật tương ứng."
    )

    @api.model
    def create(self, vals):
        # Try to auto-parse a number from the value label (e.g., '2m' -> 2.0) if not provided
        if 'price_multiplier' not in vals and vals.get('product_attribute_value_id'):
            pav = self.env['product.attribute.value'].browse(vals['product_attribute_value_id'])
            vals['price_multiplier'] = pav.default_price_multiplier or 1.0
        rec = super().create(vals)
        tmpl = rec.product_tmpl_id
        if tmpl and tmpl.use_variant_multiplier:
            tmpl._recompute_variant_extras_from_multipliers()
            tmpl._rental_sync_variant_daily_prices()
        return rec

    def write(self, vals):
        res = super().write(vals)
        if 'price_multiplier' in vals:
            for rec in self:
                tmpl = rec.product_tmpl_id
                if tmpl and tmpl.use_variant_multiplier:
                    tmpl._recompute_variant_extras_from_multipliers()
                    tmpl._rental_sync_variant_daily_prices()
        return res
