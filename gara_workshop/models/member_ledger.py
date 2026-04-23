# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class GaraMemberLedger(models.Model):
    _name = 'gara.member.ledger'
    _description = 'Gara Member Ledger'
    _order = 'entry_date desc, id desc'

    company_id = fields.Many2one(
        'res.company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Customer',
        required=True,
        index=True,
    )
    case_id = fields.Many2one(
        'gara.workshop.case',
        string='Case',
        index=True,
        ondelete='set null',
    )
    payment_id = fields.Many2one(
        'gara.workshop.payment',
        string='Payment',
        index=True,
        ondelete='set null',
    )
    entry_date = fields.Datetime(
        string='Entry Date',
        required=True,
        default=fields.Datetime.now,
        index=True,
    )
    entry_type = fields.Selection(
        [('earn', 'Earn'), ('redeem', 'Redeem'), ('adjust', 'Adjust')],
        required=True,
        default='earn',
        index=True,
    )
    points = fields.Float(required=True)
    amount_base = fields.Monetary(string='Amount Base', currency_field='currency_id')
    currency_id = fields.Many2one(related='company_id.currency_id', readonly=True)
    membership_name = fields.Char(string='Membership')
    note = fields.Text()
    state = fields.Selection(
        [('draft', 'Draft'), ('posted', 'Posted'), ('cancel', 'Cancelled')],
        required=True,
        default='posted',
        index=True,
    )
    balance_after = fields.Float(compute='_compute_balance_after')

    @api.depends('partner_id', 'points', 'state')
    def _compute_balance_after(self):
        for rec in self:
            if not rec.partner_id:
                rec.balance_after = 0.0
                continue
            lines = self.search([
                ('partner_id', '=', rec.partner_id.id),
                ('state', '=', 'posted'),
                ('id', '<=', rec.id),
            ])
            rec.balance_after = sum(lines.mapped('points'))

    @api.constrains('points', 'entry_type')
    def _check_points_sign(self):
        for rec in self:
            if rec.entry_type == 'earn' and rec.points < 0:
                raise ValidationError('Earn entries must have positive points.')
            if rec.entry_type == 'redeem' and rec.points > 0:
                raise ValidationError('Redeem entries must have negative points.')

    def action_post(self):
        self.write({'state': 'posted'})

    def action_cancel(self):
        self.write({'state': 'cancel'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})


class ResPartner(models.Model):
    _inherit = 'res.partner'

    gara_member_point_balance = fields.Float(
        string='Member Point Balance',
        compute='_compute_gara_member_point_balance',
    )

    def _compute_gara_member_point_balance(self):
        ledger = self.env['gara.member.ledger']
        for partner in self:
            total = ledger.read_group(
                [('partner_id', '=', partner.id), ('state', '=', 'posted')],
                ['points:sum'],
                [],
            )
            partner.gara_member_point_balance = total[0]['points_sum'] if total else 0.0
