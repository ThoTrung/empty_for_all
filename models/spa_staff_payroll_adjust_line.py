# -*- coding: utf-8 -*-

from odoo import fields, models


class SpaStaffPayrollLine(models.Model):
    _name = "spa.staff.payroll.line"
    _description = "Dòng phiếu lương (tổng hợp các khoản)"
    _order = "category, id"

    payroll_id = fields.Many2one(
        "spa.staff.payroll",
        string="Phiếu lương",
        required=True,
        ondelete="cascade",
        index=True,
    )
    category = fields.Selection(
        [
            ("adjustment", "Điều chỉnh / Ghi chú"),
            ("long_shift_bonus", "Thưởng ca dài"),
            ("requested_bonus", "Thưởng khách chủ động đặt"),
            ("lunch_support", "Hỗ trợ ăn trưa"),
            ("kpi_revenue", "KPI doanh thu"),
            ("sales_commission", "Thưởng bán hàng (SP)"),
            ("service_payout_session", "Tiền công (buổi làm)"),
            ("ranking_bonus", "Thưởng xếp hạng"),
            ("other", "Khác"),
        ],
        string="Loại",
        required=True,
        index=True,
    )
    code = fields.Char(string="Mã", index=True)
    name = fields.Char(string="Diễn giải", required=True)

    amount = fields.Monetary(string="Số tiền (+/-)", currency_field="currency_id")
    currency_id = fields.Many2one(
        related="payroll_id.currency_id",
        store=True,
        readonly=True,
    )

    is_manual = fields.Boolean(string="Nhập tay", default=False, index=True)
    note = fields.Text(string="Ghi chú")

    source_model = fields.Char(string="Model nguồn")
    source_id = fields.Integer(string="ID nguồn")
