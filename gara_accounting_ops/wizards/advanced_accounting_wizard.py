# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class GaraDocumentRenumberWizard(models.TransientModel):
    _name = 'gara.document.renumber.wizard'
    _description = 'KGara-style Document Renumber Wizard'

    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, required=True)
    journal_id = fields.Many2one('account.journal', required=True, domain="[('company_id', '=', company_id)]")
    date_from = fields.Date(required=True)
    date_to = fields.Date(required=True)
    prefix = fields.Char(required=True, default='CT/%(y)s/')
    padding = fields.Integer(default=5, required=True)
    next_number = fields.Integer(default=1, required=True)
    move_count = fields.Integer(compute='_compute_move_count')

    def _domain_moves(self):
        return [
            ('company_id', '=', self.company_id.id),
            ('journal_id', '=', self.journal_id.id),
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
            ('state', '=', 'draft'),
        ]

    @api.depends('company_id', 'journal_id', 'date_from', 'date_to')
    def _compute_move_count(self):
        for wizard in self:
            wizard.move_count = self.env['account.move'].search_count(wizard._domain_moves()) if wizard.journal_id else 0

    def action_apply(self):
        self.ensure_one()
        if self.date_to < self.date_from:
            raise UserError(_('Date To must be after Date From.'))
        number = self.next_number
        for move in self.env['account.move'].search(self._domain_moves(), order='date, id'):
            move.name = '%s%s' % (self.prefix, str(number).zfill(self.padding))
            number += 1
        return {'type': 'ir.actions.act_window_close'}


class GaraProductCostRecomputeWizard(models.TransientModel):
    _name = 'gara.product.cost.recompute.wizard'
    _description = 'KGara-style Product Cost Recompute Wizard'

    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, required=True)
    product_ids = fields.Many2many('product.product', required=True)
    method = fields.Selection(
        [('valuation_average', 'Average Stock Valuation'), ('current_standard', 'Keep Current Cost')],
        default='valuation_average',
        required=True,
    )
    line_ids = fields.One2many('gara.product.cost.recompute.line', 'wizard_id')

    def action_compute(self):
        self.ensure_one()
        lines = [(5, 0, 0)]
        valuation_model = self.env.get('stock.valuation.layer')
        for product in self.product_ids:
            new_cost = product.standard_price
            if self.method == 'valuation_average' and valuation_model:
                layers = valuation_model.search([
                    ('company_id', '=', self.company_id.id),
                    ('product_id', '=', product.id),
                    ('remaining_qty', '>', 0),
                ])
                qty = sum(layers.mapped('remaining_qty'))
                value = sum(layers.mapped('remaining_value'))
                if qty:
                    new_cost = value / qty
            lines.append((0, 0, {
                'product_id': product.id,
                'old_cost': product.standard_price,
                'new_cost': new_cost,
            }))
        self.line_ids = lines
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_apply(self):
        self.ensure_one()
        for line in self.line_ids:
            line.product_id.with_company(self.company_id).standard_price = line.new_cost
        return {'type': 'ir.actions.act_window_close'}


class GaraProductCostRecomputeLine(models.TransientModel):
    _name = 'gara.product.cost.recompute.line'
    _description = 'KGara Product Cost Recompute Line'

    wizard_id = fields.Many2one('gara.product.cost.recompute.wizard', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', readonly=True)
    old_cost = fields.Float(readonly=True)
    new_cost = fields.Float()


class GaraClosingEntryWizard(models.TransientModel):
    _name = 'gara.closing.entry.wizard'
    _description = 'KGara-style Closing Entry Wizard'

    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, required=True)
    date_from = fields.Date(required=True)
    date_to = fields.Date(required=True)
    config_ids = fields.Many2many('gara.closing.config', domain="[('company_id', '=', company_id)]")
    ref = fields.Char(default='KGara closing entry')

    def action_create_entries(self):
        self.ensure_one()
        if self.date_to < self.date_from:
            raise UserError(_('Date To must be after Date From.'))
        moves = self.env['account.move']
        configs = self.config_ids or self.env['gara.closing.config'].search([
            ('company_id', '=', self.company_id.id),
            ('active', '=', True),
        ])
        for config in configs:
            if not config.journal_id or not config.destination_account_id or not config.source_account_ids:
                continue
            lines = []
            total_balance = 0.0
            for account in config.source_account_ids:
                grouped = self.env['account.move.line'].read_group([
                    ('company_id', '=', self.company_id.id),
                    ('account_id', '=', account.id),
                    ('date', '>=', self.date_from),
                    ('date', '<=', self.date_to),
                    ('move_id.state', '=', 'posted'),
                ], ['balance:sum'], [])
                balance = grouped[0]['balance'] if grouped else 0.0
                if not balance:
                    continue
                total_balance += balance
                lines.append((0, 0, {
                    'name': _('Close %s') % account.display_name,
                    'account_id': account.id,
                    'debit': -balance if balance < 0 else 0.0,
                    'credit': balance if balance > 0 else 0.0,
                }))
            if not lines or not total_balance:
                continue
            lines.append((0, 0, {
                'name': config.name,
                'account_id': config.destination_account_id.id,
                'debit': total_balance if total_balance > 0 else 0.0,
                'credit': -total_balance if total_balance < 0 else 0.0,
            }))
            moves |= self.env['account.move'].create({
                'move_type': 'entry',
                'company_id': self.company_id.id,
                'journal_id': config.journal_id.id,
                'date': self.date_to,
                'ref': self.ref,
                'line_ids': lines,
            })
        if not moves:
            raise UserError(_('No closing entries were generated. Check configurations and posted move lines.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Closing Entries'),
            'res_model': 'account.move',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', moves.ids)],
        }
