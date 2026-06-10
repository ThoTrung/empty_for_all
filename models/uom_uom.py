# -*- coding: utf-8 -*-
from odoo import fields, models


class UomUom(models.Model):
    _inherit = "uom.uom"

    is_linear_meter_variant = fields.Boolean(
        string="Biến thẻ theo mét dài",
        default=False,
        help="Bật cho đơn vị gốc Mét dài. Sản phẩm dùng ĐVT này sẽ có cột Tổng MD "
             "trên bảng xác nhận khối lượng.",
    )
