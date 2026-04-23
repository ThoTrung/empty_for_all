# -*- coding: utf-8 -*-

from odoo import fields, models, tools


class GaraTAccountReport(models.Model):
    _name = 'gara.t.account.report'
    _description = 'Gara T-Account Report'
    _auto = False
    _order = 'date desc, move_id desc, id desc'

    date = fields.Date(readonly=True)
    company_id = fields.Many2one('res.company', readonly=True)
    move_id = fields.Many2one('account.move', readonly=True)
    journal_id = fields.Many2one('account.journal', readonly=True)
    account_id = fields.Many2one('account.account', readonly=True)
    account_code = fields.Char(readonly=True)
    account_name = fields.Char(readonly=True)
    partner_id = fields.Many2one('res.partner', readonly=True)
    name = fields.Char(readonly=True)
    ref = fields.Char(readonly=True)
    debit_side = fields.Monetary(currency_field='currency_id', readonly=True)
    credit_side = fields.Monetary(currency_field='currency_id', readonly=True)
    balance = fields.Monetary(currency_field='currency_id', readonly=True)
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
                    aml.account_id AS account_id,
                    account.code AS account_code,
                    account.name AS account_name,
                    aml.partner_id AS partner_id,
                    aml.name AS name,
                    move.ref AS ref,
                    aml.debit AS debit_side,
                    aml.credit AS credit_side,
                    aml.balance AS balance,
                    company.currency_id AS currency_id
                FROM account_move_line aml
                JOIN account_move move ON move.id = aml.move_id
                JOIN account_account account ON account.id = aml.account_id
                JOIN res_company company ON company.id = aml.company_id
                WHERE move.state = 'posted'
                  AND aml.account_id IS NOT NULL
                  AND COALESCE(aml.display_type, 'product') NOT IN ('line_section', 'line_note')
            )
        """ % self._table)
