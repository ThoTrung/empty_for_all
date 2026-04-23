# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class GaraApprovalRequestStep(models.Model):
    _name = 'gara.approval.request.step'
    _description = 'Gara approval request chain step'
    _order = 'request_id, sequence, id'

    request_id = fields.Many2one(
        'gara.approval.request',
        required=True,
        ondelete='cascade',
        index=True,
    )
    sequence = fields.Integer(required=True, default=10)
    approver_id = fields.Many2one('res.users', required=True, string='Approver')
    state = fields.Selection(
        [('pending', 'Pending'), ('approved', 'Approved')],
        default='pending',
        required=True,
    )


class GaraApprovalRequest(models.Model):
    _name = 'gara.approval.request'
    _description = 'Gara approval request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(required=True, default='New', copy=False)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    request_type = fields.Selection(
        [
            ('case_close', 'Case close'),
            ('insurance', 'Insurance approval'),
            ('quote', 'Quotation approval'),
        ],
        required=True,
    )
    case_id = fields.Many2one('gara.workshop.case', ondelete='cascade')
    insurance_claim_id = fields.Many2one('gara.insurance.claim', ondelete='cascade')
    sale_order_id = fields.Many2one('sale.order', ondelete='cascade')
    requester_id = fields.Many2one('res.users', required=True, default=lambda self: self.env.user)
    approver_id = fields.Many2one('res.users', string='Current approver')
    step_ids = fields.One2many('gara.approval.request.step', 'request_id', string='Approval chain')
    current_step_index = fields.Integer(string='Current step index', default=0, copy=False)
    approval_progress = fields.Char(compute='_compute_approval_progress')
    state = fields.Selection(
        [('draft', 'Draft'), ('submitted', 'Submitted'), ('approved', 'Approved'), ('rejected', 'Rejected')],
        default='draft',
        tracking=True,
        index=True,
    )
    reason = fields.Text()
    decision_note = fields.Text()
    amount_total = fields.Monetary(currency_field='currency_id')
    currency_id = fields.Many2one(related='company_id.currency_id', store=True)

    @api.depends('step_ids', 'current_step_index')
    def _compute_approval_progress(self):
        for rec in self:
            n = len(rec.step_ids)
            if n:
                rec.approval_progress = '%s / %s' % (min(rec.current_step_index + 1, n), n)
            else:
                rec.approval_progress = ''

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('gara.approval.request') or 'New'
        return super().create(vals_list)

    def _find_matching_policy(self):
        self.ensure_one()
        domain = [
            ('active', '=', True),
            ('company_id', '=', self.company_id.id),
            ('request_type', '=', self.request_type),
            ('min_amount', '<=', self.amount_total or 0.0),
            '|',
            ('max_amount', '=', False),
            ('max_amount', '>=', self.amount_total or 0.0),
        ]
        return self.env['gara.approval.policy'].search(domain, limit=1)

    def _resolve_approver_user(self, group, user):
        if user:
            return user
        if group:
            found = self.env['res.users'].search(
                [('groups_id', 'in', group.id), ('share', '=', False)],
                limit=1,
            )
            return found
        return self.env['res.users']

    def _build_steps_from_policy(self, policy):
        self.ensure_one()
        self.step_ids.unlink()
        approvers = []
        for group, user in policy._iter_approver_entries():
            u = self._resolve_approver_user(group, user)
            if not u:
                raise UserError(
                    _('No user found for an approval step on policy "%s". Configure a user or group member.')
                    % policy.display_name
                )
            approvers.append(u)
        if not approvers:
            raise UserError(
                _('Policy "%s" has no approval steps. Add lines or legacy approvers.')
                % policy.display_name
            )
        seq = 10
        lines = []
        for u in approvers:
            lines.append((0, 0, {'sequence': seq, 'approver_id': u.id, 'state': 'pending'}))
            seq += 10
        self.step_ids = lines
        self.current_step_index = 0
        self.approver_id = approvers[0].id

    def action_submit(self):
        for rec in self:
            if rec.state != 'draft':
                continue
            policy = rec._find_matching_policy()
            if policy:
                rec._build_steps_from_policy(policy)
            elif not rec.approver_id:
                manager_group = self.env.ref('gara_workshop.group_gara_role_manager', raise_if_not_found=False)
                if manager_group:
                    default_approver = self.env['res.users'].search([
                        ('groups_id', 'in', manager_group.id),
                        ('share', '=', False),
                        ('company_ids', 'in', rec.company_id.id),
                    ], limit=1)
                    if default_approver:
                        rec.approver_id = default_approver.id
            rec.state = 'submitted'

    def _check_decision_access(self):
        self.ensure_one()
        steps = self.step_ids.sorted('sequence')
        if steps:
            if self.current_step_index >= len(steps):
                raise UserError(_('Invalid approval step.'))
            step = steps[self.current_step_index]
            if step.approver_id != self.env.user:
                raise UserError(_('Only assigned approver can decide this request.'))
            return steps, step
        if self.approver_id and self.approver_id != self.env.user:
            raise UserError(_('Only assigned approver can decide this request.'))
        return steps, self.env['gara.approval.request.step']

    def action_approve(self):
        for rec in self:
            if rec.state != 'submitted':
                raise UserError(_('Only submitted requests can be approved.'))
            steps, step = rec._check_decision_access()
            if step:
                step.state = 'approved'
                if rec.current_step_index + 1 < len(steps):
                    rec.current_step_index += 1
                    rec.approver_id = steps[rec.current_step_index].approver_id
                    continue
            if rec.request_type == 'insurance' and not self.env.user.has_group('gara_workshop.group_gara_role_manager'):
                raise UserError(_('Only Gara Manager can give final approval to insurance requests.'))
            rec.state = 'approved'
            if rec.case_id and rec.request_type == 'case_close':
                rec.case_id.with_user(rec.requester_id).action_close()
            if rec.insurance_claim_id and rec.request_type == 'insurance':
                rec.insurance_claim_id.state = 'approved'
            if rec.sale_order_id and rec.request_type == 'quote':
                rec.sale_order_id._gara_mark_quote_approved(approved_by=self.env.user)

    def action_reject(self):
        for rec in self:
            if rec.state != 'submitted':
                raise UserError(_('Only submitted requests can be rejected.'))
            rec._check_decision_access()
            rec.state = 'rejected'
            if rec.sale_order_id and rec.request_type == 'quote':
                reject_reason = rec.decision_note or rec.reason or ''
                rec.sale_order_id._gara_mark_quote_rejected(reject_reason=reject_reason)
