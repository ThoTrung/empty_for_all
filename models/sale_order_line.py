# -*- coding: utf-8 -*-
from odoo import api, fields, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    staff_display_uom_id = fields.Many2one(
        "uom.uom",
        string="Đơn vị hiển thị",
        compute="_compute_staff_display_uom_id",
        readonly=True,
        help="ĐVT ưu tiên hiển thị cho NV (từ biến thể). Đơn vị tính thực tế của dòng vẫn là ĐVT đặt hàng.",
    )

    @api.depends(
        "display_type",
        "product_id",
        "product_id.staff_display_uom_id",
        "product_id.uom_id",
    )
    def _compute_staff_display_uom_id(self):
        for line in self:
            if line.display_type or not line.product_id:
                line.staff_display_uom_id = False
            else:
                line.staff_display_uom_id = line.product_id._get_staff_display_uom()
