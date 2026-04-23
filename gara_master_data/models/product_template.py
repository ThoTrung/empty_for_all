# -*- coding: utf-8 -*-

from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    gara_product_type_id = fields.Many2one(
        'gara.product.type',
        string='Gara Product Type',
        index=True,
    )
