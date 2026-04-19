# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class ProductProduct(models.Model):
    _inherit = "product.product"

    # Related for domain only: nested ``uom_id.category_id`` breaks OWL Domain when falsy.
    staff_uom_category_id = fields.Many2one(
        "uom.category",
        related="uom_id.category_id",
        string="Nhóm ĐVT (mẫu)",
        readonly=True,
    )
    staff_display_uom_id = fields.Many2one(
        "uom.uom",
        string="Đơn vị hiển thị (NV)",
        domain="[('category_id', '=?', staff_uom_category_id)]",
        help="Chỉ dùng để hiển thị cho nhân viên trên đơn hàng, phiếu vận chuyển, v.v. "
             "Để trống thì dùng Đơn vị tính trên mẫu sản phẩm. Kho vẫn dùng ĐVT mẫu.",
    )

    compensation_price = fields.Float(
        string="Compensation Price",
        compute="_compute_compensation_price",
        store=True,  # store for searching/sorting; drop to False if you prefer runtime only
        help="Template compensation price multiplied by this variant's attribute multipliers.",
    )
    rental_price_day = fields.Float(
        string="Giá thuê theo ngày",
        digits="Product Price",
        tracking=True,
        help="Giá thuê một ngày cho biến thể này. Mặc định theo mẫu (giá/ngày mẫu × lst_price / list_price mẫu); có thể sửa tay.",
    )

    def _rental_apply_daily_from_template(self):
        """Đồng bộ giá/ngày biến thể từ mẫu theo tỷ lệ giá tháng biến thể / giá tháng mẫu."""
        for prod in self:
            tmpl = prod.product_tmpl_id
            if not tmpl:
                continue
            lp = tmpl.list_price or 0.0
            base = tmpl.rental_price_day or 0.0
            if lp and base:
                prod.rental_price_day = base * (prod.lst_price / lp)
            elif base:
                prod.rental_price_day = base
            else:
                prod.rental_price_day = 0.0

    @api.depends(
        "product_tmpl_id.compensation_price",
        "product_template_attribute_value_ids.price_multiplier",
    )
    def _compute_compensation_price(self):
        company = self.env.company
        for prod in self:
            tmpl = prod.product_tmpl_id.with_company(company)
            base = tmpl.compensation_price or 0.0
            # Multiply all multipliers on this variant (works even if only one attribute, e.g., Length)
            mult = 1.0
            for v in prod.product_template_attribute_value_ids:
                m = v.price_multiplier or 1.0
                # ignore non-positive/invalid values defensively
                mult *= m if m > 0 else 1.0
            prod.compensation_price = base * mult

    def _get_staff_display_uom(self):
        """UoM shown to staff; logistics still use template ``uom_id``."""
        self.ensure_one()
        return self.staff_display_uom_id or self.uom_id

    def write(self, vals):
        res = super().write(vals)
        if "lst_price" in vals and "rental_price_day" not in vals:
            for prod in self:
                tmpl = prod.product_tmpl_id
                if not tmpl or not tmpl.rental_price_day:
                    continue
                lp = tmpl.list_price or 0.0
                base = tmpl.rental_price_day
                nd = base * (prod.lst_price / lp) if lp else base
                super(ProductProduct, prod).write({"rental_price_day": nd})
        return res

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if "staff_display_uom_id" not in vals:
                tmpl_id = vals.get("product_tmpl_id")
                if tmpl_id:
                    tmpl = self.env["product.template"].browse(tmpl_id)
                    if tmpl.exists() and tmpl.uom_id:
                        vals["staff_display_uom_id"] = tmpl.uom_id.id
        products = super().create(vals_list)
        for i, p in enumerate(products):
            vals = vals_list[i] if i < len(vals_list) else {}
            if "rental_price_day" in vals:
                continue
            tmpl = p.product_tmpl_id
            if not tmpl:
                continue
            lp = tmpl.list_price or 0.0
            base = tmpl.rental_price_day or 0.0
            if lp and base:
                p.rental_price_day = base * (p.lst_price / lp)
            elif base:
                p.rental_price_day = base
        return products


class ProductAttributeValue(models.Model):
    _inherit = "product.attribute.value"

    default_price_multiplier = fields.Float(
        string="Default Price Multiplier",
        default=1.0,
        help="Default multiplier used to initialize product-specific multipliers "
             "when this value is added to a product."
    )
