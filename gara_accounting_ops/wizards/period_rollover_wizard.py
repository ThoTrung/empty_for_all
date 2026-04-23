# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare, float_is_zero


class GaraPeriodRolloverWizard(models.TransientModel):
    _name = 'gara.period.rollover.wizard'
    _description = 'KGara-style data period rollover wizard'

    company_id = fields.Many2one(
        'res.company',
        required=True,
        default=lambda self: self.env.company,
    )
    closing_date = fields.Date(required=True)
    opening_date = fields.Date(required=True)
    journal_id = fields.Many2one(
        'account.journal',
        required=True,
        domain="[('company_id', '=', company_id), ('type', '=', 'general')]",
        default=lambda self: self.env['account.journal'].search([
            ('company_id', '=', self.env.company.id),
            ('type', '=', 'general'),
        ], limit=1),
    )
    ref = fields.Char(default='Data rollover opening entry')
    include_partner_details = fields.Boolean(
        string='Split receivable/payable by partner',
        default=True,
    )
    lock_previous_period = fields.Boolean(
        string='Lock previous period after rollover',
        default=True,
    )
    post_move = fields.Boolean(string='Post opening entry after creation')
    line_ids = fields.One2many('gara.period.rollover.wizard.line', 'wizard_id')
    currency_id = fields.Many2one(related='company_id.currency_id', readonly=True)

    @api.onchange('closing_date')
    def _onchange_closing_date(self):
        for wizard in self:
            if wizard.closing_date and (
                not wizard.opening_date or wizard.opening_date <= wizard.closing_date
            ):
                wizard.opening_date = fields.Date.add(wizard.closing_date, days=1)

    def _check_dates(self):
        self.ensure_one()
        if self.opening_date <= self.closing_date:
            raise UserError(_('Opening date must be after closing date.'))

    def _balance_to_amounts(self, balance):
        if balance >= 0:
            return balance, 0.0
        return 0.0, -balance

    def _prepare_rollover_lines(self):
        self.ensure_one()
        aml_model = self.env['account.move.line']
        account_model = self.env['account.account']
        currency = self.company_id.currency_id
        base_domain = [
            ('company_id', '=', self.company_id.id),
            ('date', '<=', self.closing_date),
            ('move_id.state', '=', 'posted'),
            ('account_id.include_initial_balance', '=', True),
        ]
        grouped_accounts = aml_model.read_group(
            base_domain,
            ['balance:sum'],
            ['account_id'],
            lazy=False,
        )
        line_vals = []
        for grouped in grouped_accounts:
            account_data = grouped.get('account_id')
            if not account_data:
                continue
            account = account_model.browse(account_data[0])
            balance = grouped.get('balance') or 0.0
            if float_is_zero(balance, precision_rounding=currency.rounding):
                continue
            if (
                self.include_partner_details
                and account.account_type in ('asset_receivable', 'liability_payable')
            ):
                partner_domain = list(base_domain)
                partner_domain.append(('account_id', '=', account.id))
                grouped_partners = aml_model.read_group(
                    partner_domain,
                    ['balance:sum'],
                    ['partner_id'],
                    lazy=False,
                )
                partner_balance_total = 0.0
                for grouped_partner in grouped_partners:
                    partner_balance = grouped_partner.get('balance') or 0.0
                    if float_is_zero(partner_balance, precision_rounding=currency.rounding):
                        continue
                    partner_balance_total += partner_balance
                    partner_data = grouped_partner.get('partner_id')
                    partner_id = partner_data[0] if partner_data else False
                    partner_name = partner_data[1] if partner_data else _('No Partner')
                    debit, credit = self._balance_to_amounts(partner_balance)
                    line_vals.append({
                        'account_id': account.id,
                        'partner_id': partner_id,
                        'name': '%s / %s' % (account.display_name, partner_name),
                        'balance': partner_balance,
                        'debit': debit,
                        'credit': credit,
                    })
                remainder = balance - partner_balance_total
                if not float_is_zero(remainder, precision_rounding=currency.rounding):
                    debit, credit = self._balance_to_amounts(remainder)
                    line_vals.append({
                        'account_id': account.id,
                        'name': '%s / %s' % (account.display_name, _('No Partner')),
                        'balance': remainder,
                        'debit': debit,
                        'credit': credit,
                    })
                continue
            debit, credit = self._balance_to_amounts(balance)
            line_vals.append({
                'account_id': account.id,
                'name': account.display_name,
                'balance': balance,
                'debit': debit,
                'credit': credit,
            })
        return line_vals

    def action_prepare_lines(self):
        self.ensure_one()
        self._check_dates()
        line_vals = self._prepare_rollover_lines()
        if not line_vals:
            raise UserError(_('No carry-forward balance found up to the selected closing date.'))
        self.write({
            'line_ids': [(5, 0, 0)] + [(0, 0, vals) for vals in line_vals],
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_create_move(self):
        self.ensure_one()
        self._check_dates()
        if not self.line_ids:
            self.action_prepare_lines()
        if not self.line_ids:
            raise UserError(_('There are no rollover lines to create the opening entry.'))
        total_debit = sum(self.line_ids.mapped('debit'))
        total_credit = sum(self.line_ids.mapped('credit'))
        if float_compare(
            total_debit,
            total_credit,
            precision_rounding=self.company_id.currency_id.rounding,
        ):
            raise UserError(_('Opening entry is not balanced. Please review rollover lines.'))
        move = self.env['account.move'].create({
            'move_type': 'entry',
            'company_id': self.company_id.id,
            'journal_id': self.journal_id.id,
            'date': self.opening_date,
            'ref': self.ref,
            'line_ids': [
                (0, 0, {
                    'account_id': line.account_id.id,
                    'partner_id': line.partner_id.id,
                    'name': line.name or line.account_id.display_name,
                    'debit': line.debit,
                    'credit': line.credit,
                })
                for line in self.line_ids
            ],
            'gara_document_note': _('Opening entry created from rollover wizard.'),
        })
        if self.post_move:
            move.action_post()
        if self.lock_previous_period and (
            not self.company_id.period_lock_date
            or self.closing_date > self.company_id.period_lock_date
        ):
            self.company_id.period_lock_date = self.closing_date
        return {
            'type': 'ir.actions.act_window',
            'name': _('Rollover Opening Entry'),
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': move.id,
        }


class GaraPeriodRolloverWizardLine(models.TransientModel):
    _name = 'gara.period.rollover.wizard.line'
    _description = 'KGara data period rollover line'

    wizard_id = fields.Many2one(
        'gara.period.rollover.wizard',
        required=True,
        ondelete='cascade',
    )
    company_id = fields.Many2one(related='wizard_id.company_id')
    account_id = fields.Many2one(
        'account.account',
        required=True,
        domain="[('company_id', '=', company_id), ('deprecated', '=', False)]",
    )
    partner_id = fields.Many2one('res.partner')
    name = fields.Char()
    balance = fields.Monetary(currency_field='currency_id', readonly=True)
    debit = fields.Monetary(currency_field='currency_id')
    credit = fields.Monetary(currency_field='currency_id')
    currency_id = fields.Many2one(related='wizard_id.currency_id', readonly=True)

    @api.constrains('debit', 'credit')
    def _check_debit_credit(self):
        for line in self:
            if line.debit < 0 or line.credit < 0:
                raise ValidationError(_('Debit/Credit must be non-negative.'))
            if line.debit and line.credit:
                raise ValidationError(_('A rollover line cannot have both debit and credit.'))
