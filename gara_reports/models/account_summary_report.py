# -*- coding: utf-8 -*-

from odoo import fields, models, tools


class GaraAccountSummaryReport(models.Model):
    _name = 'gara.account.summary.report'
    _description = 'Gara Account Summary Report'
    _auto = False
    _order = 'report_date desc, account_id'

    report_date = fields.Date(readonly=True)
    company_id = fields.Many2one('res.company', readonly=True)
    account_id = fields.Many2one('account.account', readonly=True)
    account_code = fields.Char(readonly=True)
    account_name = fields.Char(readonly=True)
    account_type = fields.Char(readonly=True)
    account_internal_group = fields.Char(readonly=True)
    debit = fields.Monetary(currency_field='currency_id', readonly=True)
    credit = fields.Monetary(currency_field='currency_id', readonly=True)
    balance = fields.Monetary(currency_field='currency_id', readonly=True)
    move_line_count = fields.Integer(readonly=True)
    currency_id = fields.Many2one('res.currency', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    ROW_NUMBER() OVER (ORDER BY period.report_date DESC, period.account_id) AS id,
                    period.report_date,
                    period.company_id,
                    period.account_id,
                    period.account_code,
                    period.account_name,
                    period.account_type,
                    period.account_internal_group,
                    period.debit,
                    period.credit,
                    period.balance,
                    period.move_line_count,
                    company.currency_id
                FROM (
                    SELECT
                        DATE_TRUNC('month', aml.date)::date AS report_date,
                        aml.company_id,
                        aml.account_id,
                        account.code AS account_code,
                        account.name AS account_name,
                        account.account_type AS account_type,
                        account.internal_group AS account_internal_group,
                        SUM(aml.debit) AS debit,
                        SUM(aml.credit) AS credit,
                        SUM(aml.balance) AS balance,
                        COUNT(aml.id) AS move_line_count
                    FROM account_move_line aml
                    JOIN account_move move ON move.id = aml.move_id
                    JOIN account_account account ON account.id = aml.account_id
                    WHERE move.state = 'posted'
                      AND aml.account_id IS NOT NULL
                      AND COALESCE(aml.display_type, 'product') NOT IN ('line_section', 'line_note')
                    GROUP BY
                        DATE_TRUNC('month', aml.date)::date,
                        aml.company_id,
                        aml.account_id,
                        account.code,
                        account.name,
                        account.account_type,
                        account.internal_group
                ) period
                JOIN res_company company ON company.id = period.company_id
            )
        """ % self._table)
