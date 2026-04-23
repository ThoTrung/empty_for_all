# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class GaraAllocationPlan(models.Model):
    _name = 'gara.allocation.plan'
    _description = 'Gara Allocation Plan'
    _order = 'company_id, sequence, name'

    name = fields.Char(required=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    source_account_id = fields.Many2one(
        'account.account',
        required=True,
        check_company=True,
        domain="[('deprecated', '=', False)]",
    )
    journal_id = fields.Many2one(
        'account.journal',
        required=True,
        check_company=True,
        domain="[('company_id', '=', company_id), ('type', '=', 'general')]",
    )
    method = fields.Selection(
        [('percent', 'Percent'), ('fixed', 'Fixed Amount')],
        default='percent',
        required=True,
    )
    line_ids = fields.One2many('gara.allocation.plan.line', 'plan_id')
    execution_ids = fields.One2many('gara.allocation.execution', 'plan_id')
    execution_count = fields.Integer(compute='_compute_execution_count')
    note = fields.Text()

    @api.depends('execution_ids')
    def _compute_execution_count(self):
        for plan in self:
            plan.execution_count = len(plan.execution_ids)

    def action_open_run_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Run Allocation'),
            'res_model': 'gara.allocation.run.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_plan_id': self.id, 'default_company_id': self.company_id.id},
        }

    def action_view_executions(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Allocation Executions'),
            'res_model': 'gara.allocation.execution',
            'view_mode': 'tree,form',
            'domain': [('plan_id', '=', self.id)],
        }


class GaraAllocationPlanLine(models.Model):
    _name = 'gara.allocation.plan.line'
    _description = 'Gara Allocation Plan Line'
    _order = 'plan_id, sequence, id'

    plan_id = fields.Many2one('gara.allocation.plan', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    name = fields.Char(required=True)
    destination_account_id = fields.Many2one(
        'account.account',
        required=True,
        check_company=True,
        domain="[('deprecated', '=', False)]",
    )
    percent = fields.Float(default=0.0)
    fixed_amount = fields.Monetary(default=0.0)
    company_id = fields.Many2one(related='plan_id.company_id', store=True, readonly=True)
    currency_id = fields.Many2one(related='company_id.currency_id', readonly=True)

    @api.constrains('percent', 'fixed_amount')
    def _check_values(self):
        for line in self:
            if line.plan_id.method == 'percent' and line.percent <= 0:
                raise ValidationError(_('Percent allocation lines must have a positive percent.'))
            if line.plan_id.method == 'fixed' and line.fixed_amount <= 0:
                raise ValidationError(_('Fixed allocation lines must have a positive amount.'))


class GaraAllocationExecution(models.Model):
    _name = 'gara.allocation.execution'
    _description = 'Gara Allocation Execution'
    _order = 'date desc, id desc'

    name = fields.Char(required=True)
    plan_id = fields.Many2one('gara.allocation.plan', required=True, ondelete='restrict')
    company_id = fields.Many2one(related='plan_id.company_id', store=True, readonly=True)
    date_from = fields.Date(required=True)
    date_to = fields.Date(required=True)
    date = fields.Date(required=True)
    source_balance = fields.Monetary(readonly=True)
    amount = fields.Monetary(readonly=True)
    currency_id = fields.Many2one(related='company_id.currency_id', readonly=True)
    move_id = fields.Many2one('account.move', readonly=True)
    line_ids = fields.One2many('gara.allocation.execution.line', 'execution_id')

    def action_view_move(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Allocation Journal Entry'),
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': self.move_id.id,
        }


class GaraAllocationExecutionLine(models.Model):
    _name = 'gara.allocation.execution.line'
    _description = 'Gara Allocation Execution Line'
    _order = 'execution_id, sequence, id'

    execution_id = fields.Many2one('gara.allocation.execution', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    name = fields.Char(required=True)
    destination_account_id = fields.Many2one('account.account', required=True, readonly=True)
    percent = fields.Float(readonly=True)
    amount = fields.Monetary(readonly=True)
    currency_id = fields.Many2one(related='execution_id.currency_id', readonly=True)


class GaraAllocationRunWizard(models.TransientModel):
    _name = 'gara.allocation.run.wizard'
    _description = 'Gara Allocation Run Wizard'

    plan_id = fields.Many2one('gara.allocation.plan', required=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, required=True)
    date_from = fields.Date(required=True)
    date_to = fields.Date(required=True)
    date = fields.Date(default=fields.Date.context_today, required=True)
    ref = fields.Char(default='KGara allocation')
    source_balance = fields.Monetary(readonly=True)
    currency_id = fields.Many2one(related='company_id.currency_id', readonly=True)
    line_ids = fields.One2many('gara.allocation.run.wizard.line', 'wizard_id')

    @api.onchange('plan_id')
    def _onchange_plan_id(self):
        for wizard in self:
            wizard.company_id = wizard.plan_id.company_id

    def _get_source_balance(self):
        self.ensure_one()
        grouped = self.env['account.move.line'].read_group([
            ('company_id', '=', self.company_id.id),
            ('account_id', '=', self.plan_id.source_account_id.id),
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
            ('move_id.state', '=', 'posted'),
        ], ['balance:sum'], [])
        return grouped[0]['balance'] if grouped else 0.0

    def action_prepare_lines(self):
        self.ensure_one()
        if self.date_to < self.date_from:
            raise UserError(_('Date To must be after Date From.'))
        if not self.plan_id.line_ids:
            raise UserError(_('The allocation plan has no lines.'))
        source_balance = self._get_source_balance()
        base_amount = abs(source_balance)
        lines = [(5, 0, 0)]
        for plan_line in self.plan_id.line_ids:
            amount = base_amount * plan_line.percent / 100.0 if self.plan_id.method == 'percent' else plan_line.fixed_amount
            if amount:
                lines.append((0, 0, {
                    'name': plan_line.name,
                    'destination_account_id': plan_line.destination_account_id.id,
                    'percent': plan_line.percent,
                    'amount': amount,
                    'sequence': plan_line.sequence,
                }))
        self.write({'source_balance': source_balance, 'line_ids': lines})
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_create_move(self):
        self.ensure_one()
        if not self.line_ids:
            self.action_prepare_lines()
        if not self.line_ids:
            raise UserError(_('There is no allocation amount to post.'))
        total = sum(self.line_ids.mapped('amount'))
        if total <= 0:
            raise UserError(_('Allocation amount must be positive.'))
        balance_sign = 1 if self.source_balance >= 0 else -1
        line_vals = []
        for line in self.line_ids:
            line_vals.append((0, 0, {
                'name': line.name,
                'account_id': line.destination_account_id.id,
                'debit': line.amount if balance_sign > 0 else 0.0,
                'credit': line.amount if balance_sign < 0 else 0.0,
            }))
        line_vals.append((0, 0, {
            'name': self.plan_id.source_account_id.display_name,
            'account_id': self.plan_id.source_account_id.id,
            'debit': total if balance_sign < 0 else 0.0,
            'credit': total if balance_sign > 0 else 0.0,
        }))
        move = self.env['account.move'].create({
            'move_type': 'entry',
            'company_id': self.company_id.id,
            'journal_id': self.plan_id.journal_id.id,
            'date': self.date,
            'ref': self.ref,
            'line_ids': line_vals,
        })
        execution = self.env['gara.allocation.execution'].create({
            'name': self.ref or self.plan_id.name,
            'plan_id': self.plan_id.id,
            'date_from': self.date_from,
            'date_to': self.date_to,
            'date': self.date,
            'source_balance': self.source_balance,
            'amount': total,
            'move_id': move.id,
            'line_ids': [
                (0, 0, {
                    'name': line.name,
                    'destination_account_id': line.destination_account_id.id,
                    'percent': line.percent,
                    'amount': line.amount,
                    'sequence': line.sequence,
                })
                for line in self.line_ids
            ],
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Allocation Execution'),
            'res_model': 'gara.allocation.execution',
            'view_mode': 'form',
            'res_id': execution.id,
        }


class GaraAllocationRunWizardLine(models.TransientModel):
    _name = 'gara.allocation.run.wizard.line'
    _description = 'Gara Allocation Run Wizard Line'
    _order = 'wizard_id, sequence, id'

    wizard_id = fields.Many2one('gara.allocation.run.wizard', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    name = fields.Char(required=True)
    destination_account_id = fields.Many2one('account.account', required=True, readonly=True)
    percent = fields.Float(readonly=True)
    amount = fields.Monetary()
    currency_id = fields.Many2one(related='wizard_id.currency_id', readonly=True)
