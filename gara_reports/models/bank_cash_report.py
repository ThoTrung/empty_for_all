# -*- coding: utf-8 -*-

from odoo import fields, models, tools


class GaraBankCashReport(models.Model):
    _name = 'gara.bank.cash.report'
    _description = 'Gara Bank/Cash Report'
    _auto = False
    _order = 'date desc, id desc'

    date = fields.Date(readonly=True)
    company_id = fields.Many2one('res.company', readonly=True)
    move_id = fields.Many2one('account.move', readonly=True)
    journal_id = fields.Many2one('account.journal', readonly=True)
    journal_type = fields.Char(readonly=True)
    account_id = fields.Many2one('account.account', readonly=True)
    partner_id = fields.Many2one('res.partner', readonly=True)
    name = fields.Char(readonly=True)
    ref = fields.Char(readonly=True)
    debit = fields.Monetary(currency_field='currency_id', readonly=True)
    credit = fields.Monetary(currency_field='currency_id', readonly=True)
    balance = fields.Monetary(currency_field='currency_id', readonly=True)
    amount_currency = fields.Monetary(currency_field='transaction_currency_id', readonly=True)
    transaction_currency_id = fields.Many2one('res.currency', readonly=True)
    currency_id = fields.Many2one('res.currency', readonly=True)

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
                    journal.type AS journal_type,
                    aml.account_id AS account_id,
                    aml.partner_id AS partner_id,
                    aml.name AS name,
                    move.ref AS ref,
                    aml.debit AS debit,
                    aml.credit AS credit,
                    aml.balance AS balance,
                    aml.amount_currency AS amount_currency,
                    aml.currency_id AS transaction_currency_id,
                    company.currency_id AS currency_id
                FROM account_move_line aml
                JOIN account_move move ON move.id = aml.move_id
                JOIN account_journal journal ON journal.id = aml.journal_id
                JOIN res_company company ON company.id = aml.company_id
                WHERE move.state = 'posted'
                  AND journal.type IN ('bank', 'cash')
                  AND aml.account_id IS NOT NULL
                  AND COALESCE(aml.display_type, 'product') NOT IN ('line_section', 'line_note')
            )
        """ % self._table)
