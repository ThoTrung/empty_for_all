# -*- coding: utf-8 -*-

from odoo import fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_compare


class GaraOpeningBalanceWizard(models.TransientModel):
    _name = 'gara.opening.balance.wizard'
    _description = 'KGara-style opening balance import'

    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    date = fields.Date(required=True, default=fields.Date.context_today)
    journal_id = fields.Many2one(
        'account.journal',
        required=True,
        domain="[('company_id', '=', company_id), ('type', '=', 'general')]",
        default=lambda self: self.env['account.journal'].search([
            ('company_id', '=', self.env.company.id),
            ('type', '=', 'general'),
        ], limit=1),
    )
    ref = fields.Char(default='Opening balance')
    post_move = fields.Boolean(string='Post after creation')
    line_ids = fields.One2many('gara.opening.balance.wizard.line', 'wizard_id')

    def action_create_move(self):
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_('Add at least one opening balance line.'))
        debit = sum(self.line_ids.mapped('debit'))
        credit = sum(self.line_ids.mapped('credit'))
        if float_compare(debit, credit, precision_rounding=self.company_id.currency_id.rounding):
            raise UserError(_('Opening balance must be balanced before creating a journal entry.'))
        move = self.env['account.move'].create({
            'move_type': 'entry',
            'company_id': self.company_id.id,
            'journal_id': self.journal_id.id,
            'date': self.date,
            'ref': self.ref,
            'line_ids': [
                (0, 0, {
                    'account_id': line.account_id.id,
                    'partner_id': line.partner_id.id,
                    'name': line.name or self.ref or '/',
                    'debit': line.debit,
                    'credit': line.credit,
                })
                for line in self.line_ids
            ],
            'gara_document_note': _('Opening balance created from KGara-style wizard.'),
        })
        if self.post_move:
            move.action_post()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Opening Balance Entry'),
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': move.id,
        }


class GaraOpeningBalanceWizardLine(models.TransientModel):
    _name = 'gara.opening.balance.wizard.line'
    _description = 'KGara opening balance line'

    wizard_id = fields.Many2one('gara.opening.balance.wizard', required=True, ondelete='cascade')
    company_id = fields.Many2one(related='wizard_id.company_id')
    account_id = fields.Many2one(
        'account.account',
        required=True,
        domain="[('company_id', '=', company_id), ('deprecated', '=', False)]",
    )
    partner_id = fields.Many2one('res.partner')
    name = fields.Char()
    debit = fields.Float()
    credit = fields.Float()
