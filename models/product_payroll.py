# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ProductCategory(models.Model):
    _inherit = "product.category"

    spa_sales_commission_percent = fields.Float(
        string="% thưởng bán hàng",
        digits="Discount",
        help="Áp dụng cho sản phẩm thuộc danh mục này. "
        "Nếu danh mục con để 0, hệ thống leo lên danh mục cha đến khi tìm thấy % > 0.",
    )


class SpaProductPayrollProfile(models.Model):
    _name = "spa.product.payroll.profile"
    _description = "Cấu hình lương/thưởng theo sản phẩm (Spa payroll)"

    name = fields.Char(string="Tên", required=True)
    company_id = fields.Many2one(
        "res.company",
        string="Công ty",
        required=False,
        index=True,
        help="Để trống: mọi công ty đều dùng được. Có giá trị: chỉ công ty đó.",
    )
    payout_line_ids = fields.One2many(
        "spa.product.service.payout.line",
        "profile_id",
        string="Tiền công theo cấp",
    )

    def action_copy_profile(self):
        self.ensure_one()
        copy = self.copy({"name": _("%s (sao chép)") % self.name})
        return {
            "type": "ir.actions.act_window",
            "res_model": "spa.product.payroll.profile",
            "res_id": copy.id,
            "view_mode": "form",
            "target": "current",
        }


class SpaProductServicePayoutLine(models.Model):
    _name = "spa.product.service.payout.line"
    _description = "Tiền công thực hiện dịch vụ theo cấp nhân viên"
    _order = "sequence, id"

    profile_id = fields.Many2one(
        "spa.product.payroll.profile",
        string="Profile payroll",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(default=10)
    staff_level_id = fields.Many2one(
        "spa.staff.level",
        string="Cấp nhân viên",
        required=True,
        ondelete="restrict",
        index=True,
    )
    amount_fixed = fields.Monetary(
        string="Tiền cố định",
        currency_field="currency_id",
        default=0.0,
    )
    percent = fields.Float(
        string="%",
        digits="Discount",
        help="Phần trăm áp dụng theo `product.template.list_price` (tạm thời; có thể đổi chuẩn sau).",
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Tiền tệ",
        compute="_compute_currency_id",
        store=True,
        readonly=True,
    )

    _sql_constraints = [
        (
            "uniq_profile_staff_level",
            "unique(profile_id, staff_level_id)",
            "Mỗi profile chỉ được cấu hình một dòng cho một cấp nhân viên.",
        )
    ]

    @api.depends("profile_id", "profile_id.company_id", "profile_id.company_id.currency_id")
    def _compute_currency_id(self):
        for rec in self:
            company = rec.profile_id.company_id
            rec.currency_id = (
                company.currency_id
                if company
                else rec.env.company.currency_id
            )

    @api.constrains("amount_fixed", "percent")
    def _check_amounts(self):
        for rec in self:
            if (rec.amount_fixed or 0.0) < 0:
                raise ValidationError(_("Tiền cố định không được âm."))
            if (rec.percent or 0.0) < 0:
                raise ValidationError(_("% không được âm."))


class ProductTemplate(models.Model):
    _inherit = "product.template"

    spa_payroll_profile_id = fields.Many2one(
        "spa.product.payroll.profile",
        string="Profile lương Spa",
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        help="Gom cấu hình tiền công theo cấp. Profile không chọn công ty dùng được mọi công ty.",
    )
    spa_payroll_profile_payout_line_ids = fields.One2many(
        related="spa_payroll_profile_id.payout_line_ids",
        string="Tiền công theo cấp (readonly)",
        readonly=True,
    )
    spa_sales_commission_percent = fields.Float(
        string="% thưởng bán hàng (theo SP)",
        digits="Discount",
        help="[Ẩn UI] Legacy — không dùng khi tính lương. "
        "Nguồn hiện tại: % trên danh mục sản phẩm (product.category).",
    )

    def _spa_get_sales_commission_percent(self):
        """% hoa hồng từ danh mục SP, leo parent nếu danh mục hiện tại = 0."""
        self.ensure_one()
        categ = self.categ_id
        while categ:
            pct = float(categ.spa_sales_commission_percent or 0.0)
            if pct > 0:
                return pct
            categ = categ.parent_id
        return 0.0
