# -*- coding: utf-8 -*-

from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    spa_booking_is_hair_removal = fields.Boolean(
        string="Booking: Dịch vụ triệt lông",
        help="Nếu bật, các đặt lịch dịch vụ này (trạng thái Đặt lịch) sẽ có màu riêng theo cấu hình booking_calendar.",
        default=False,
    )

