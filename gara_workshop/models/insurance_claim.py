# -*- coding: utf-8 -*-

from odoo import api, fields, models


class GaraInsuranceClaim(models.Model):
    _name = 'gara.insurance.claim'
    _description = 'Insurance claim'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(default='New', required=True, copy=False, tracking=True)
    company_id = fields.Many2one(
        'res.company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    case_id = fields.Many2one('gara.workshop.case', ondelete='set null', index=True)
    partner_id = fields.Many2one('res.partner', required=True, index=True)
    vehicle_id = fields.Many2one('fleet.vehicle', required=True, index=True)
    insurer_partner_id = fields.Many2one('res.partner', string='Insurer')
    policy_number = fields.Char()
    claim_date = fields.Date(default=fields.Date.context_today, required=True)
    approved_amount = fields.Monetary(currency_field='currency_id')
    paid_amount = fields.Monetary(currency_field='currency_id')
    currency_id = fields.Many2one(related='company_id.currency_id', store=True)
    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('submitted', 'Submitted'),
            ('approved', 'Approved'),
            ('paid', 'Paid'),
            ('rejected', 'Rejected'),
        ],
        default='draft',
        tracking=True,
    )
    note = fields.Html()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('gara.insurance.claim') or 'New'
            if vals.get('case_id') and not vals.get('partner_id'):
                case = self.env['gara.workshop.case'].browse(vals['case_id'])
                vals['partner_id'] = case.partner_id.id
            if vals.get('case_id') and not vals.get('vehicle_id'):
                case = self.env['gara.workshop.case'].browse(vals['case_id'])
                vals['vehicle_id'] = case.vehicle_id.id
        return super().create(vals_list)

    def action_request_approval(self):
        self.ensure_one()
        manager_group = self.env.ref('gara_workshop.group_gara_role_manager', raise_if_not_found=False)
        manager_user = self.env['res.users']
        if manager_group:
            manager_user = self.env['res.users'].search([('groups_id', 'in', manager_group.id)], limit=1)
        req = self.env['gara.approval.request'].create({
            'request_type': 'insurance',
            'insurance_claim_id': self.id,
            'case_id': self.case_id.id,
            'company_id': self.company_id.id,
            'reason': f'Insurance approval for claim {self.name}',
            'approver_id': manager_user.id if manager_user else False,
            'amount_total': self.approved_amount,
        })
        req.action_submit()
        return req

    def action_mark_approved(self):
        for rec in self:
            threshold = rec.company_id.gara_insurance_approval_threshold or 0.0
            if threshold and rec.approved_amount > threshold:
                approved_req = self.env['gara.approval.request'].search([
                    ('insurance_claim_id', '=', rec.id),
                    ('request_type', '=', 'insurance'),
                    ('state', '=', 'approved'),
                ], limit=1)
                if not approved_req:
                    rec.action_request_approval()
                    continue
            rec.state = 'approved'
