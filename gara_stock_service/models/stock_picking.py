# -*- coding: utf-8 -*-

from odoo import fields, models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    gara_service_stock_request_id = fields.Many2one(
        'gara.service.stock.request',
        string='Gara Service Stock Request',
        copy=False,
        index=True,
    )
