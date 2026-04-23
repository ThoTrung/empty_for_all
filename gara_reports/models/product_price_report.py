# -*- coding: utf-8 -*-

from odoo import fields, models, tools


class GaraProductPriceReport(models.Model):
    _name = 'gara.product.price.report'
    _description = 'Gara Product Price Report'
    _auto = False
    _order = 'product_name'

    product_id = fields.Many2one('product.product', readonly=True)
    product_tmpl_id = fields.Many2one('product.template', readonly=True)
    product_name = fields.Char(readonly=True)
    default_code = fields.Char(readonly=True)
    barcode = fields.Char(readonly=True)
    detailed_type = fields.Char(readonly=True)
    categ_id = fields.Many2one('product.category', readonly=True)
    uom_id = fields.Many2one('uom.uom', readonly=True)
    list_price = fields.Float(readonly=True)
    variant_count = fields.Integer(readonly=True)
    pricelist_rule_count = fields.Integer(readonly=True)
    active = fields.Boolean(readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    pp.id AS id,
                    pp.id AS product_id,
                    pt.id AS product_tmpl_id,
                    pt.name AS product_name,
                    pp.default_code AS default_code,
                    pp.barcode AS barcode,
                    pt.detailed_type AS detailed_type,
                    pt.categ_id AS categ_id,
                    pt.uom_id AS uom_id,
                    pt.list_price AS list_price,
                    COUNT(DISTINCT pp.id) AS variant_count,
                    COUNT(DISTINCT pli.id) AS pricelist_rule_count,
                    pt.active AS active
                FROM product_product pp
                JOIN product_template pt ON pt.id = pp.product_tmpl_id
                LEFT JOIN product_pricelist_item pli ON pli.product_tmpl_id = pt.id
                GROUP BY
                    pp.id,
                    pt.id,
                    pt.name,
                    pp.default_code,
                    pp.barcode,
                    pt.detailed_type,
                    pt.categ_id,
                    pt.uom_id,
                    pt.list_price,
                    pt.active
            )
        """ % self._table)
