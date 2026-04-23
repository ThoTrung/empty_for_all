# -*- coding: utf-8 -*-

from odoo import fields, models, tools


class GaraStockLedgerReport(models.Model):
    _name = 'gara.stock.ledger.report'
    _description = 'Gara Stock Ledger Report'
    _auto = False
    _order = 'date desc, id desc'

    date = fields.Datetime(readonly=True)
    company_id = fields.Many2one('res.company', readonly=True)
    product_id = fields.Many2one('product.product', readonly=True)
    categ_id = fields.Many2one('product.category', string='Product Category', readonly=True)
    product_uom_id = fields.Many2one('uom.uom', readonly=True)
    picking_id = fields.Many2one('stock.picking', readonly=True)
    picking_type_id = fields.Many2one('stock.picking.type', readonly=True)
    partner_id = fields.Many2one('res.partner', readonly=True)
    location_id = fields.Many2one('stock.location', string='Source Location', readonly=True)
    location_dest_id = fields.Many2one('stock.location', string='Destination Location', readonly=True)
    origin = fields.Char(readonly=True)
    reference = fields.Char(readonly=True)
    quantity_in = fields.Float(readonly=True)
    quantity_out = fields.Float(readonly=True)
    quantity_internal = fields.Float(readonly=True)
    quantity_balance_delta = fields.Float(string='Internal Balance Delta', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    sml.id AS id,
                    sml.date AS date,
                    sml.company_id AS company_id,
                    sml.product_id AS product_id,
                    pt.categ_id AS categ_id,
                    sml.product_uom_id AS product_uom_id,
                    sml.picking_id AS picking_id,
                    sp.picking_type_id AS picking_type_id,
                    sp.partner_id AS partner_id,
                    sml.location_id AS location_id,
                    sml.location_dest_id AS location_dest_id,
                    COALESCE(sp.origin, sm.origin) AS origin,
                    sml.reference AS reference,
                    CASE
                        WHEN src.usage != 'internal' AND dest.usage = 'internal'
                        THEN sml.quantity ELSE 0.0
                    END AS quantity_in,
                    CASE
                        WHEN src.usage = 'internal' AND dest.usage != 'internal'
                        THEN sml.quantity ELSE 0.0
                    END AS quantity_out,
                    CASE
                        WHEN src.usage = 'internal' AND dest.usage = 'internal'
                        THEN sml.quantity ELSE 0.0
                    END AS quantity_internal,
                    CASE
                        WHEN src.usage != 'internal' AND dest.usage = 'internal'
                        THEN sml.quantity
                        WHEN src.usage = 'internal' AND dest.usage != 'internal'
                        THEN -sml.quantity
                        ELSE 0.0
                    END AS quantity_balance_delta
                FROM stock_move_line sml
                JOIN stock_location src ON src.id = sml.location_id
                JOIN stock_location dest ON dest.id = sml.location_dest_id
                JOIN product_product pp ON pp.id = sml.product_id
                JOIN product_template pt ON pt.id = pp.product_tmpl_id
                LEFT JOIN stock_move sm ON sm.id = sml.move_id
                LEFT JOIN stock_picking sp ON sp.id = sml.picking_id
                WHERE sml.state = 'done'
                  AND (src.usage = 'internal' OR dest.usage = 'internal')
            )
        """ % self._table)
