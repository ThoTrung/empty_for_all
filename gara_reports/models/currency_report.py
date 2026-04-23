# -*- coding: utf-8 -*-

from odoo import fields, models, tools


class GaraForeignCurrencyReport(models.Model):
    _name = 'gara.foreign.currency.report'
    _description = 'Gara Foreign Currency Report'
    _auto = False
    _order = 'date desc, id desc'

    date = fields.Date(readonly=True)
    company_id = fields.Many2one('res.company', readonly=True)
    move_id = fields.Many2one('account.move', readonly=True)
    journal_id = fields.Many2one('account.journal', readonly=True)
    account_id = fields.Many2one('account.account', readonly=True)
    partner_id = fields.Many2one('res.partner', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Transaction Currency', readonly=True)
    company_currency_id = fields.Many2one('res.currency', readonly=True)
    account_type = fields.Char(readonly=True)
    debit = fields.Monetary(currency_field='company_currency_id', readonly=True)
    credit = fields.Monetary(currency_field='company_currency_id', readonly=True)
    balance = fields.Monetary(currency_field='company_currency_id', readonly=True)
    amount_currency = fields.Monetary(currency_field='currency_id', readonly=True)
    amount_residual_currency = fields.Monetary(currency_field='currency_id', readonly=True)
    foreign_receivable = fields.Monetary(currency_field='currency_id', readonly=True)
    foreign_payable = fields.Monetary(currency_field='currency_id', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    aml.id AS id,
                    aml.date AS date,
                    aml.company_id AS company_id,
                    aml.move_id AS move_id,
                    aml.journal_id AS journal_id,
                    aml.account_id AS account_id,
                    aml.partner_id AS partner_id,
                    aml.currency_id AS currency_id,
                    company.currency_id AS company_currency_id,
                    account.account_type AS account_type,
                    aml.debit AS debit,
                    aml.credit AS credit,
                    aml.balance AS balance,
                    aml.amount_currency AS amount_currency,
                    aml.amount_residual_currency AS amount_residual_currency,
                    CASE
                        WHEN account.account_type = 'asset_receivable' THEN aml.amount_residual_currency
                        ELSE 0.0
                    END AS foreign_receivable,
                    CASE
                        WHEN account.account_type = 'liability_payable' THEN -aml.amount_residual_currency
                        ELSE 0.0
                    END AS foreign_payable
                FROM account_move_line aml
                JOIN account_move move ON move.id = aml.move_id
                JOIN account_account account ON account.id = aml.account_id
                JOIN res_company company ON company.id = aml.company_id
                WHERE move.state = 'posted'
                  AND aml.currency_id IS NOT NULL
                  AND aml.currency_id != company.currency_id
                  AND COALESCE(aml.display_type, 'product') NOT IN ('line_section', 'line_note')
            )
        """ % self._table)
