# -*- coding: utf-8 -*-

from odoo import fields, models, tools


class GaraServiceCaseReport(models.Model):
    _name = 'gara.service.case.report'
    _description = 'Gara Service Case Report'
    _auto = False
    _order = 'intake_date desc, id desc'

    case_id = fields.Many2one('gara.workshop.case', readonly=True)
    name = fields.Char(readonly=True)
    company_id = fields.Many2one('res.company', readonly=True)
    partner_id = fields.Many2one('res.partner', readonly=True)
    vehicle_id = fields.Many2one('fleet.vehicle', readonly=True)
    user_id = fields.Many2one('res.users', string='Service Advisor', readonly=True)
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('intake', 'Intake'),
            ('quoted', 'Quoted'),
            ('repair', 'Under repair'),
            ('done', 'Repair done'),
            ('invoiced', 'Invoiced'),
            ('closed', 'Closed'),
            ('cancel', 'Cancelled'),
        ],
        readonly=True,
    )
    intake_date = fields.Datetime(readonly=True)
    report_date = fields.Date(readonly=True)
    sale_order_id = fields.Many2one('sale.order', readonly=True)
    quotation_amount = fields.Monetary(currency_field='currency_id', readonly=True)
    invoiced_amount = fields.Monetary(currency_field='currency_id', readonly=True)
    residual_amount = fields.Monetary(currency_field='currency_id', readonly=True)
    payment_amount = fields.Monetary(currency_field='currency_id', readonly=True)
    stock_request_count = fields.Integer(readonly=True)
    part_quantity = fields.Float(readonly=True)
    duration_days = fields.Float(readonly=True)
    currency_id = fields.Many2one('res.currency', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    c.id AS id,
                    c.id AS case_id,
                    c.name AS name,
                    c.company_id AS company_id,
                    c.partner_id AS partner_id,
                    c.vehicle_id AS vehicle_id,
                    c.user_id AS user_id,
                    c.state AS state,
                    c.intake_date AS intake_date,
                    c.intake_date::date AS report_date,
                    c.sale_order_id AS sale_order_id,
                    COALESCE(so.amount_total, 0.0) AS quotation_amount,
                    COALESCE(inv.amount_total, 0.0) AS invoiced_amount,
                    COALESCE(inv.amount_residual, 0.0) AS residual_amount,
                    COALESCE(pay.amount, 0.0) AS payment_amount,
                    COALESCE(stock.request_count, 0) AS stock_request_count,
                    COALESCE(stock.part_quantity, 0.0) AS part_quantity,
                    CASE
                        WHEN c.intake_date IS NULL THEN 0.0
                        ELSE EXTRACT(EPOCH FROM (COALESCE(c.write_date, NOW()) - c.intake_date)) / 86400.0
                    END AS duration_days,
                    company.currency_id AS currency_id
                FROM gara_workshop_case c
                JOIN res_company company ON company.id = c.company_id
                LEFT JOIN sale_order so ON so.id = c.sale_order_id
                LEFT JOIN (
                    SELECT
                        gara_case_id,
                        SUM(amount_total) AS amount_total,
                        SUM(amount_residual) AS amount_residual
                    FROM account_move
                    WHERE move_type = 'out_invoice'
                      AND state = 'posted'
                      AND gara_case_id IS NOT NULL
                    GROUP BY gara_case_id
                ) inv ON inv.gara_case_id = c.id
                LEFT JOIN (
                    SELECT
                        case_id,
                        SUM(amount) AS amount
                    FROM gara_workshop_payment
                    GROUP BY case_id
                ) pay ON pay.case_id = c.id
                LEFT JOIN (
                    SELECT
                        req.case_id,
                        COUNT(DISTINCT req.id) AS request_count,
                        SUM(line.product_uom_qty) AS part_quantity
                    FROM gara_service_stock_request req
                    JOIN gara_service_stock_request_line line ON line.request_id = req.id
                    WHERE req.state != 'cancel'
                    GROUP BY req.case_id
                ) stock ON stock.case_id = c.id
            )
        """ % self._table)
