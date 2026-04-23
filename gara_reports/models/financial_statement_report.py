# -*- coding: utf-8 -*-

from odoo import fields, models, tools


class GaraFinancialStatementLine(models.Model):
    _name = 'gara.financial.statement.line'
    _description = 'Gara Financial Statement Line'
    _order = 'statement_type, sequence, code'

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    statement_type = fields.Selection(
        [
            ('balance_sheet', 'Balance Sheet'),
            ('income_statement', 'Income Statement'),
            ('cash_flow', 'Cash Flow'),
            ('other', 'Other'),
        ],
        default='balance_sheet',
        required=True,
    )
    account_ids = fields.Many2many(
        'account.account',
        'gara_financial_statement_line_account_rel',
        'line_id',
        'account_id',
        string='Accounts',
        domain="[('deprecated', '=', False)]",
    )
    sign = fields.Integer(default=1, required=True)
    active = fields.Boolean(default=True)
    note = fields.Text()

    _sql_constraints = [
        ('code_statement_unique', 'unique(code, statement_type)', 'The code must be unique per statement type.'),
    ]


class GaraFinancialStatementReport(models.Model):
    _name = 'gara.financial.statement.report'
    _description = 'Gara Financial Statement Report'
    _auto = False
    _order = 'report_date desc, statement_type, sequence'

    report_date = fields.Date(readonly=True)
    company_id = fields.Many2one('res.company', readonly=True)
    statement_line_id = fields.Many2one('gara.financial.statement.line', readonly=True)
    statement_type = fields.Char(readonly=True)
    code = fields.Char(readonly=True)
    name = fields.Char(readonly=True)
    sequence = fields.Integer(readonly=True)
    debit = fields.Monetary(currency_field='currency_id', readonly=True)
    credit = fields.Monetary(currency_field='currency_id', readonly=True)
    balance = fields.Monetary(currency_field='currency_id', readonly=True)
    amount = fields.Monetary(currency_field='currency_id', readonly=True)
    move_line_count = fields.Integer(readonly=True)
    currency_id = fields.Many2one('res.currency', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    ROW_NUMBER() OVER (
                        ORDER BY DATE_TRUNC('month', aml.date)::date DESC, line.statement_type, line.sequence, line.id, aml.company_id
                    ) AS id,
                    DATE_TRUNC('month', aml.date)::date AS report_date,
                    aml.company_id AS company_id,
                    line.id AS statement_line_id,
                    line.statement_type AS statement_type,
                    line.code AS code,
                    line.name AS name,
                    line.sequence AS sequence,
                    SUM(aml.debit) AS debit,
                    SUM(aml.credit) AS credit,
                    SUM(aml.balance) AS balance,
                    SUM(aml.balance * line.sign) AS amount,
                    COUNT(aml.id) AS move_line_count,
                    company.currency_id AS currency_id
                FROM gara_financial_statement_line line
                JOIN gara_financial_statement_line_account_rel rel ON rel.line_id = line.id
                JOIN account_move_line aml ON aml.account_id = rel.account_id
                JOIN account_move move ON move.id = aml.move_id
                JOIN res_company company ON company.id = aml.company_id
                WHERE line.active = TRUE
                  AND move.state = 'posted'
                  AND COALESCE(aml.display_type, 'product') NOT IN ('line_section', 'line_note')
                GROUP BY
                    DATE_TRUNC('month', aml.date)::date,
                    aml.company_id,
                    line.id,
                    line.statement_type,
                    line.code,
                    line.name,
                    line.sequence,
                    company.currency_id
            )
        """ % self._table)
