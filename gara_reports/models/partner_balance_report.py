# -*- coding: utf-8 -*-

from odoo import fields, models, tools


class GaraPartnerBalanceReport(models.Model):
    _name = 'gara.partner.balance.report'
    _description = 'Gara Partner Balance Report'
    _auto = False
    _order = 'report_date desc, partner_id'

    report_date = fields.Date(readonly=True)
    company_id = fields.Many2one('res.company', readonly=True)
    partner_id = fields.Many2one('res.partner', readonly=True)
    account_id = fields.Many2one('account.account', readonly=True)
    account_type = fields.Char(readonly=True)
    debit = fields.Monetary(currency_field='currency_id', readonly=True)
    credit = fields.Monetary(currency_field='currency_id', readonly=True)
    balance = fields.Monetary(currency_field='currency_id', readonly=True)
    residual = fields.Monetary(currency_field='currency_id', readonly=True)
    receivable_amount = fields.Monetary(currency_field='currency_id', readonly=True)
    payable_amount = fields.Monetary(currency_field='currency_id', readonly=True)
    currency_id = fields.Many2one('res.currency', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    ROW_NUMBER() OVER (ORDER BY period.report_date DESC, period.partner_id, period.account_id) AS id,
                    period.report_date,
                    period.company_id,
                    period.partner_id,
                    period.account_id,
                    period.account_type,
                    period.debit,
                    period.credit,
                    period.balance,
                    period.residual,
                    CASE
                        WHEN period.account_type = 'asset_receivable' THEN period.residual
                        ELSE 0.0
                    END AS receivable_amount,
                    CASE
                        WHEN period.account_type = 'liability_payable' THEN -period.residual
                        ELSE 0.0
                    END AS payable_amount,
                    company.currency_id
                FROM (
                    SELECT
                        DATE_TRUNC('month', aml.date)::date AS report_date,
                        aml.company_id,
                        aml.partner_id,
                        aml.account_id,
                        account.account_type AS account_type,
                        SUM(aml.debit) AS debit,
                        SUM(aml.credit) AS credit,
                        SUM(aml.balance) AS balance,
                        SUM(aml.amount_residual) AS residual
                    FROM account_move_line aml
                    JOIN account_move move ON move.id = aml.move_id
                    JOIN account_account account ON account.id = aml.account_id
                    WHERE move.state = 'posted'
                      AND aml.partner_id IS NOT NULL
                      AND account.account_type IN ('asset_receivable', 'liability_payable')
                      AND COALESCE(aml.display_type, 'product') NOT IN ('line_section', 'line_note')
                    GROUP BY
                        DATE_TRUNC('month', aml.date)::date,
                        aml.company_id,
                        aml.partner_id,
                        aml.account_id,
                        account.account_type
                ) period
                JOIN res_company company ON company.id = period.company_id
            )
        """ % self._table)
