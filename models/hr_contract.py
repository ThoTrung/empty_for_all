# -*- coding: utf-8 -*-

from odoo import fields, models


class HrContract(models.Model):
    _inherit = "hr.contract"

    spa_overtime_hourly_rate = fields.Monetary(
        string="Lương làm thêm / giờ",
        currency_field="currency_id",
        help="Áp dụng khi duyệt làm thêm giờ và tính phiếu lương.",
    )
