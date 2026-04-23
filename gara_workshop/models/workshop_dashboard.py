# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class GaraWorkshopDashboard(models.TransientModel):
    _name = 'gara.workshop.dashboard'
    _description = 'Gara workshop role dashboard'

    company_id = fields.Many2one(
        'res.company',
        required=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(related='company_id.currency_id')
    stat_cases_open = fields.Integer(compute='_compute_stats')
    stat_cases_mine = fields.Integer(compute='_compute_stats')
    stat_payments_today = fields.Monetary(compute='_compute_stats', currency_field='currency_id')
    stat_invoices_residual = fields.Monetary(compute='_compute_stats', currency_field='currency_id')
    stat_approvals_my_pending = fields.Integer(compute='_compute_stats')

    @api.depends('company_id')
    def _compute_stats(self):
        today = fields.Date.context_today(self)
        Case = self.env['gara.workshop.case']
        Pay = self.env['gara.workshop.payment']
        Move = self.env['account.move']
        Appr = self.env['gara.approval.request']
        for rec in self:
            cid = rec.company_id.id
            rec.stat_cases_open = Case.search_count([
                ('company_id', '=', cid),
                ('state', 'not in', ('closed', 'cancel')),
            ])
            rec.stat_cases_mine = Case.search_count([
                ('company_id', '=', cid),
                ('user_id', '=', self.env.uid),
                ('state', 'not in', ('closed', 'cancel')),
            ])
            pays = Pay.search([('company_id', '=', cid), ('payment_date', '=', today)])
            rec.stat_payments_today = sum(pays.mapped('amount'))
            invs = Move.search([
                ('company_id', '=', cid),
                ('state', '=', 'posted'),
                ('move_type', '=', 'out_invoice'),
                ('payment_state', 'not in', ('paid', 'in_payment')),
                ('gara_case_id', '!=', False),
            ])
            rec.stat_invoices_residual = sum(invs.mapped('amount_residual'))
            rec.stat_approvals_my_pending = Appr.search_count([
                ('company_id', '=', cid),
                ('state', '=', 'submitted'),
                ('approver_id', '=', self.env.uid),
            ])

    def action_open_cases_open(self):
        self.ensure_one()
        return self._action_window(
            _('Open cases'),
            'gara.workshop.case',
            [('company_id', '=', self.company_id.id), ('state', 'not in', ('closed', 'cancel'))],
        )

    def action_open_cases_mine(self):
        self.ensure_one()
        return self._action_window(
            _('My cases'),
            'gara.workshop.case',
            [
                ('company_id', '=', self.company_id.id),
                ('user_id', '=', self.env.uid),
                ('state', 'not in', ('closed', 'cancel')),
            ],
        )

    def action_open_payments_today(self):
        self.ensure_one()
        today = fields.Date.context_today(self)
        return self._action_window(
            _("Today's payments"),
            'gara.workshop.payment',
            [('company_id', '=', self.company_id.id), ('payment_date', '=', today)],
        )

    def action_open_invoices_residual(self):
        self.ensure_one()
        return self._action_window(
            _('Gara invoices — balance due'),
            'account.move',
            [
                ('company_id', '=', self.company_id.id),
                ('state', '=', 'posted'),
                ('move_type', '=', 'out_invoice'),
                ('payment_state', 'not in', ('paid', 'in_payment')),
                ('gara_case_id', '!=', False),
            ],
        )

    def action_open_my_approvals(self):
        self.ensure_one()
        return self._action_window(
            _('My pending approvals'),
            'gara.approval.request',
            [
                ('company_id', '=', self.company_id.id),
                ('state', '=', 'submitted'),
                ('approver_id', '=', self.env.uid),
            ],
        )

    def _action_window(self, title, res_model, domain):
        return {
            'type': 'ir.actions.act_window',
            'name': title,
            'res_model': res_model,
            'view_mode': 'tree,form',
            'domain': domain,
            'context': {'default_company_id': self.company_id.id},
        }
