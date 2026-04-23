# -*- coding: utf-8 -*-

from odoo import fields, models, tools


class GaraBiMonthlyKpi(models.Model):
    _name = 'gara.bi.monthly.kpi'
    _description = 'Gara BI Monthly KPI'
    _auto = False
    _order = 'report_date desc, company_id'

    report_date = fields.Date(readonly=True)
    company_id = fields.Many2one('res.company', readonly=True)
    case_count = fields.Integer(readonly=True)
    closed_case_count = fields.Integer(readonly=True)
    cancelled_case_count = fields.Integer(readonly=True)
    quotation_amount = fields.Monetary(currency_field='currency_id', readonly=True)
    invoiced_amount = fields.Monetary(currency_field='currency_id', readonly=True)
    residual_amount = fields.Monetary(currency_field='currency_id', readonly=True)
    payment_amount = fields.Monetary(currency_field='currency_id', readonly=True)
    stock_request_count = fields.Integer(readonly=True)
    part_quantity = fields.Float(readonly=True)
    avg_duration_days = fields.Float(readonly=True)
    currency_id = fields.Many2one('res.currency', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    ROW_NUMBER() OVER (ORDER BY DATE_TRUNC('month', report.report_date)::date DESC, report.company_id) AS id,
                    DATE_TRUNC('month', report.report_date)::date AS report_date,
                    report.company_id AS company_id,
                    COUNT(report.case_id) AS case_count,
                    SUM(CASE WHEN report.state = 'closed' THEN 1 ELSE 0 END) AS closed_case_count,
                    SUM(CASE WHEN report.state = 'cancel' THEN 1 ELSE 0 END) AS cancelled_case_count,
                    SUM(report.quotation_amount) AS quotation_amount,
                    SUM(report.invoiced_amount) AS invoiced_amount,
                    SUM(report.residual_amount) AS residual_amount,
                    SUM(report.payment_amount) AS payment_amount,
                    SUM(report.stock_request_count) AS stock_request_count,
                    SUM(report.part_quantity) AS part_quantity,
                    AVG(report.duration_days) AS avg_duration_days,
                    report.currency_id AS currency_id
                FROM gara_service_case_report report
                WHERE report.report_date IS NOT NULL
                GROUP BY
                    DATE_TRUNC('month', report.report_date)::date,
                    report.company_id,
                    report.currency_id
            )
        """ % self._table)


class GaraBiManagementSummary(models.Model):
    _name = 'gara.bi.management.summary'
    _description = 'Gara BI Management Summary'
    _auto = False
    _order = 'report_date desc, company_id'

    report_date = fields.Date(readonly=True)
    company_id = fields.Many2one('res.company', readonly=True)
    case_count = fields.Integer(readonly=True)
    open_case_count = fields.Integer(readonly=True)
    closed_case_count = fields.Integer(readonly=True)
    cancelled_case_count = fields.Integer(readonly=True)
    invoiced_amount = fields.Monetary(currency_field='currency_id', readonly=True)
    payment_amount = fields.Monetary(currency_field='currency_id', readonly=True)
    residual_amount = fields.Monetary(currency_field='currency_id', readonly=True)
    part_quantity = fields.Float(readonly=True)
    avg_duration_days = fields.Float(readonly=True)
    revenue_per_case = fields.Monetary(currency_field='currency_id', readonly=True)
    collection_rate = fields.Float(readonly=True)
    close_rate = fields.Float(readonly=True)
    cancel_rate = fields.Float(readonly=True)
    currency_id = fields.Many2one('res.currency', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    monthly.id AS id,
                    monthly.report_date AS report_date,
                    monthly.company_id AS company_id,
                    monthly.case_count AS case_count,
                    monthly.case_count - monthly.closed_case_count - monthly.cancelled_case_count AS open_case_count,
                    monthly.closed_case_count AS closed_case_count,
                    monthly.cancelled_case_count AS cancelled_case_count,
                    monthly.invoiced_amount AS invoiced_amount,
                    monthly.payment_amount AS payment_amount,
                    monthly.residual_amount AS residual_amount,
                    monthly.part_quantity AS part_quantity,
                    monthly.avg_duration_days AS avg_duration_days,
                    CASE
                        WHEN monthly.case_count = 0 THEN 0.0
                        ELSE monthly.invoiced_amount / monthly.case_count
                    END AS revenue_per_case,
                    CASE
                        WHEN monthly.invoiced_amount = 0 THEN 0.0
                        ELSE monthly.payment_amount / monthly.invoiced_amount * 100.0
                    END AS collection_rate,
                    CASE
                        WHEN monthly.case_count = 0 THEN 0.0
                        ELSE monthly.closed_case_count::numeric / monthly.case_count * 100.0
                    END AS close_rate,
                    CASE
                        WHEN monthly.case_count = 0 THEN 0.0
                        ELSE monthly.cancelled_case_count::numeric / monthly.case_count * 100.0
                    END AS cancel_rate,
                    monthly.currency_id AS currency_id
                FROM gara_bi_monthly_kpi monthly
            )
        """ % self._table)
