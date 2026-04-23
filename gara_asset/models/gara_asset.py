# -*- coding: utf-8 -*-

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class GaraAssetCategory(models.Model):
    _name = 'gara.asset.category'
    _description = 'Gara Asset Category'
    _order = 'sequence, name'

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, required=True)
    currency_id = fields.Many2one(related='company_id.currency_id', readonly=True)
    asset_account_id = fields.Many2one(
        'account.account',
        string='Asset Account',
        required=True,
        domain="[('deprecated', '=', False)]",
    )
    depreciation_account_id = fields.Many2one(
        'account.account',
        string='Accumulated Depreciation Account',
        required=True,
        domain="[('deprecated', '=', False)]",
    )
    expense_account_id = fields.Many2one(
        'account.account',
        string='Depreciation Expense Account',
        required=True,
        domain="[('deprecated', '=', False)]",
    )
    journal_id = fields.Many2one(
        'account.journal',
        string='Depreciation Journal',
        required=True,
        domain="[('type', '=', 'general')]",
    )
    default_method_number = fields.Integer(default=12, required=True)
    default_period_months = fields.Integer(default=1, required=True)
    active = fields.Boolean(default=True)

    @api.constrains('default_method_number', 'default_period_months')
    def _check_defaults(self):
        for category in self:
            if category.default_method_number <= 0:
                raise ValidationError(_('Number of depreciation periods must be positive.'))
            if category.default_period_months <= 0:
                raise ValidationError(_('Depreciation period length must be positive.'))


class GaraAsset(models.Model):
    _name = 'gara.asset'
    _description = 'Gara Fixed Asset'
    _order = 'acquisition_date desc, name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(required=True, tracking=True)
    code = fields.Char(copy=False, tracking=True)
    category_id = fields.Many2one('gara.asset.category', required=True, tracking=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, required=True)
    currency_id = fields.Many2one(related='company_id.currency_id', readonly=True)
    acquisition_date = fields.Date(default=fields.Date.context_today, required=True)
    first_depreciation_date = fields.Date(default=fields.Date.context_today, required=True)
    original_value = fields.Monetary(required=True, tracking=True)
    salvage_value = fields.Monetary(default=0.0)
    method_number = fields.Integer(required=True, default=12)
    period_months = fields.Integer(required=True, default=1)
    note = fields.Text()
    schedule_ids = fields.One2many('gara.asset.depreciation.line', 'asset_id', copy=False)
    move_ids = fields.One2many('account.move', 'gara_asset_id', readonly=True)
    accumulated_depreciation = fields.Monetary(compute='_compute_amounts', store=True)
    residual_value = fields.Monetary(compute='_compute_amounts', store=True)
    state = fields.Selection(
        [('draft', 'Draft'), ('running', 'Running'), ('closed', 'Closed'), ('cancel', 'Cancelled')],
        default='draft',
        required=True,
        tracking=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        sequence = self.env['ir.sequence']
        for vals in vals_list:
            if not vals.get('code'):
                vals['code'] = sequence.next_by_code('gara.asset') or _('New')
        return super().create(vals_list)

    @api.onchange('category_id')
    def _onchange_category_id(self):
        for asset in self:
            if asset.category_id:
                asset.method_number = asset.category_id.default_method_number
                asset.period_months = asset.category_id.default_period_months

    @api.depends('original_value', 'salvage_value', 'schedule_ids.amount', 'schedule_ids.move_id.state')
    def _compute_amounts(self):
        for asset in self:
            posted_lines = asset.schedule_ids.filtered(lambda line: line.move_id.state == 'posted')
            asset.accumulated_depreciation = sum(posted_lines.mapped('amount'))
            asset.residual_value = asset.original_value - asset.accumulated_depreciation

    @api.constrains('original_value', 'salvage_value', 'method_number', 'period_months')
    def _check_values(self):
        for asset in self:
            if asset.original_value <= 0.0:
                raise ValidationError(_('Original value must be positive.'))
            if asset.salvage_value < 0.0:
                raise ValidationError(_('Salvage value must not be negative.'))
            if asset.salvage_value >= asset.original_value:
                raise ValidationError(_('Salvage value must be lower than original value.'))
            if asset.method_number <= 0:
                raise ValidationError(_('Number of depreciation periods must be positive.'))
            if asset.period_months <= 0:
                raise ValidationError(_('Depreciation period length must be positive.'))

    def action_confirm(self):
        for asset in self:
            if asset.state != 'draft':
                continue
            asset._generate_depreciation_schedule()
            asset.state = 'running'

    def action_reset_draft(self):
        for asset in self:
            if asset.schedule_ids.filtered('move_id'):
                raise UserError(_('You cannot reset an asset that already has depreciation entries.'))
            asset.schedule_ids.unlink()
            asset.state = 'draft'

    def action_close(self):
        self.write({'state': 'closed'})

    def action_cancel(self):
        for asset in self:
            if asset.move_ids.filtered(lambda move: move.state == 'posted'):
                raise UserError(_('You cannot cancel an asset with posted depreciation entries.'))
            asset.schedule_ids.filtered(lambda line: line.move_id and line.move_id.state == 'draft').move_id.unlink()
            asset.schedule_ids.unlink()
            asset.state = 'cancel'

    def action_create_depreciation_moves(self):
        for asset in self:
            asset.schedule_ids.filtered(lambda line: line.state == 'draft').action_create_move()

    def _generate_depreciation_schedule(self):
        self.ensure_one()
        self.schedule_ids.unlink()
        depreciable_value = self.original_value - self.salvage_value
        base_amount = self.currency_id.round(depreciable_value / self.method_number)
        total_amount = 0.0
        commands = []
        for index in range(self.method_number):
            amount = base_amount
            if index == self.method_number - 1:
                amount = depreciable_value - total_amount
            total_amount += amount
            commands.append((0, 0, {
                'sequence': index + 1,
                'depreciation_date': self.first_depreciation_date + relativedelta(months=index * self.period_months),
                'amount': amount,
            }))
        self.write({'schedule_ids': commands})


class GaraAssetDepreciationLine(models.Model):
    _name = 'gara.asset.depreciation.line'
    _description = 'Gara Asset Depreciation Line'
    _order = 'asset_id, sequence'

    asset_id = fields.Many2one('gara.asset', required=True, ondelete='cascade')
    sequence = fields.Integer(required=True)
    depreciation_date = fields.Date(required=True)
    amount = fields.Monetary(required=True)
    company_id = fields.Many2one(related='asset_id.company_id', store=True, readonly=True)
    currency_id = fields.Many2one(related='asset_id.currency_id', readonly=True)
    move_id = fields.Many2one('account.move', readonly=True, copy=False)
    state = fields.Selection(
        [('draft', 'Draft'), ('move_created', 'Move Created'), ('posted', 'Posted')],
        compute='_compute_state',
        store=True,
    )

    @api.depends('move_id', 'move_id.state')
    def _compute_state(self):
        for line in self:
            if not line.move_id:
                line.state = 'draft'
            elif line.move_id.state == 'posted':
                line.state = 'posted'
            else:
                line.state = 'move_created'

    def action_create_move(self):
        for line in self:
            if line.move_id:
                continue
            asset = line.asset_id
            category = asset.category_id
            line.move_id = self.env['account.move'].create({
                'move_type': 'entry',
                'date': line.depreciation_date,
                'journal_id': category.journal_id.id,
                'ref': '%s - %s' % (asset.code or asset.name, line.sequence),
                'gara_asset_id': asset.id,
                'line_ids': [
                    (0, 0, {
                        'name': _('Depreciation %s') % asset.name,
                        'account_id': category.expense_account_id.id,
                        'debit': line.amount,
                        'credit': 0.0,
                    }),
                    (0, 0, {
                        'name': _('Accumulated depreciation %s') % asset.name,
                        'account_id': category.depreciation_account_id.id,
                        'debit': 0.0,
                        'credit': line.amount,
                    }),
                ],
            })


class AccountMove(models.Model):
    _inherit = 'account.move'

    gara_asset_id = fields.Many2one('gara.asset', string='Zgara Asset', copy=False, readonly=True)
