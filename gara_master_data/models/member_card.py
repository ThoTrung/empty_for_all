# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class GaraMemberCard(models.Model):
    _name = 'gara.member.card'
    _description = 'Gara Member Card'
    _order = 'id desc'

    name = fields.Char(
        string='Card Number',
        required=True,
        copy=False,
        default='New',
        index=True,
    )
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
    membership_type_id = fields.Many2one(
        'gara.membership.type',
        string='Membership Type',
        required=True,
        ondelete='restrict',
    )
    issue_date = fields.Date(
        string='Issue Date',
        required=True,
        default=fields.Date.context_today,
    )
    expiry_date = fields.Date(string='Expiry Date')
    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('active', 'Active'),
            ('blocked', 'Blocked'),
            ('expired', 'Expired'),
            ('cancel', 'Cancelled'),
        ],
        required=True,
        default='active',
        index=True,
    )
    active = fields.Boolean(default=True)
    note = fields.Text()
    ledger_entry_ids = fields.One2many(
        'gara.member.ledger',
        'card_id',
        string='Ledger Entries',
    )
    points_earned = fields.Float(compute='_compute_points')
    points_redeemed = fields.Float(compute='_compute_points')
    point_balance = fields.Float(compute='_compute_points')

    _sql_constraints = [
        (
            'card_number_company_unique',
            'unique(name, company_id)',
            'Card number must be unique per company.',
        ),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('gara.member.card') or 'New'
        cards = super().create(vals_list)
        cards._sync_partner_membership_type()
        return cards

    def write(self, vals):
        res = super().write(vals)
        if {'partner_id', 'membership_type_id', 'state', 'active'}.intersection(vals):
            self._sync_partner_membership_type()
        return res

    @api.depends('ledger_entry_ids.points', 'ledger_entry_ids.state')
    def _compute_points(self):
        for card in self:
            posted_lines = card.ledger_entry_ids.filtered(lambda line: line.state == 'posted')
            earned = sum(posted_lines.filtered(lambda line: line.points > 0).mapped('points'))
            redeemed = abs(sum(posted_lines.filtered(lambda line: line.points < 0).mapped('points')))
            card.points_earned = earned
            card.points_redeemed = redeemed
            card.point_balance = earned - redeemed

    @api.constrains('issue_date', 'expiry_date')
    def _check_expiry_date(self):
        for rec in self:
            if rec.expiry_date and rec.issue_date and rec.expiry_date < rec.issue_date:
                raise ValidationError('Expiry date cannot be earlier than issue date.')

    @api.constrains('partner_id', 'state', 'active')
    def _check_single_active_card(self):
        for rec in self:
            if rec.state != 'active' or not rec.active:
                continue
            another_active = self.search_count([
                ('id', '!=', rec.id),
                ('partner_id', '=', rec.partner_id.id),
                ('state', '=', 'active'),
                ('active', '=', True),
            ])
            if another_active:
                raise ValidationError('A customer can only have one active membership card.')

    def _sync_partner_membership_type(self):
        partners = self.mapped('partner_id')
        if not partners:
            return
        for partner in partners:
            active_card = self.search([
                ('partner_id', '=', partner.id),
                ('state', '=', 'active'),
                ('active', '=', True),
            ], order='issue_date desc, id desc', limit=1)
            if active_card and partner.gara_membership_type_id != active_card.membership_type_id:
                partner.gara_membership_type_id = active_card.membership_type_id

    def action_activate(self):
        for rec in self:
            if rec.expiry_date and rec.expiry_date < fields.Date.context_today(self):
                raise ValidationError('Cannot activate an expired membership card.')
        self.write({'state': 'active', 'active': True})

    def action_block(self):
        self.write({'state': 'blocked'})

    def action_expire(self):
        self.write({'state': 'expired'})

    def action_cancel(self):
        self.write({'state': 'cancel'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})


class GaraMemberLedger(models.Model):
    _inherit = 'gara.member.ledger'

    card_id = fields.Many2one(
        'gara.member.card',
        string='Member Card',
        index=True,
        ondelete='set null',
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            partner_id = vals.get('partner_id')
            if partner_id and not vals.get('card_id'):
                card = self.env['gara.member.card'].search([
                    ('partner_id', '=', partner_id),
                    ('state', '=', 'active'),
                    ('active', '=', True),
                ], order='issue_date desc, id desc', limit=1)
                if card:
                    vals['card_id'] = card.id
                    vals.setdefault('membership_name', card.membership_type_id.display_name)
        return super().create(vals_list)

    @api.constrains('card_id', 'partner_id', 'company_id')
    def _check_card_partner_company(self):
        for rec in self:
            if not rec.card_id:
                continue
            if rec.partner_id and rec.card_id.partner_id != rec.partner_id:
                raise ValidationError('Member card must belong to the same customer.')
            if rec.company_id and rec.card_id.company_id != rec.company_id:
                raise ValidationError('Member card must belong to the same company.')


class ResPartner(models.Model):
    _inherit = 'res.partner'

    gara_member_card_ids = fields.One2many(
        'gara.member.card',
        'partner_id',
        string='Member Cards',
    )
    gara_active_member_card_id = fields.Many2one(
        'gara.member.card',
        string='Active Member Card',
        compute='_compute_gara_active_member_card',
    )
    gara_member_card_count = fields.Integer(
        string='Member Card Count',
        compute='_compute_gara_active_member_card',
    )

    def _compute_gara_active_member_card(self):
        Card = self.env['gara.member.card']
        for partner in self:
            active_card = Card.search([
                ('partner_id', '=', partner.id),
                ('state', '=', 'active'),
                ('active', '=', True),
            ], order='issue_date desc, id desc', limit=1)
            partner.gara_active_member_card_id = active_card
            partner.gara_member_card_count = Card.search_count([('partner_id', '=', partner.id)])
