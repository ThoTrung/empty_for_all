# -*- coding: utf-8 -*-
from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    zalo_optout = fields.Boolean(
        string="Không nhận tin Zalo",
        help="Bật để ngừng gửi mọi tin Zalo (ZNS) tự động cho khách hàng này.",
    )
