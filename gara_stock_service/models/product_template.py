# -*- coding: utf-8 -*-

from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    gara_min_qty = fields.Float(string='Gara Min Quantity')
    gara_max_qty = fields.Float(string='Gara Max Quantity')
    gara_below_min_qty = fields.Boolean(
        string='Below Gara Min Quantity',
        compute='_compute_gara_stock_level_flags',
        search='_search_gara_below_min_qty',
    )

    @api.depends('qty_available', 'gara_min_qty')
    def _compute_gara_stock_level_flags(self):
        for product in self:
            product.gara_below_min_qty = (
                product.gara_min_qty > 0
                and product.qty_available <= product.gara_min_qty
            )

    def _search_gara_below_min_qty(self, operator, value):
        if operator not in ('=', '!='):
            return [('id', '=', 0)]
        expected = bool(value)
        if operator == '!=':
            expected = not expected
        products = self.search([
            ('type', 'in', ('product', 'consu')),
            ('gara_min_qty', '>', 0),
        ])
        ids = products.filtered(lambda product: product.qty_available <= product.gara_min_qty).ids
        return [('id', 'in' if expected else 'not in', ids)]
