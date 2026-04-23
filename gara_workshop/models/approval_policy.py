# -*- coding: utf-8 -*-

from odoo import fields, models


class GaraApprovalPolicyLine(models.Model):
    _name = 'gara.approval.policy.line'
    _description = 'Gara approval policy step (ordered approvers)'
    _order = 'policy_id, sequence, id'

    policy_id = fields.Many2one(
        'gara.approval.policy',
        required=True,
        ondelete='cascade',
    )
    sequence = fields.Integer(default=10)
    approver_group_id = fields.Many2one('res.groups', string='Approver group')
    approver_user_id = fields.Many2one('res.users', string='Approver user')


class GaraApprovalPolicy(models.Model):
    _name = 'gara.approval.policy'
    _description = 'Gara approval policy by amount range'
    _order = 'request_type, min_amount, id'

    name = fields.Char(required=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    active = fields.Boolean(default=True)
    request_type = fields.Selection(
        [
            ('case_close', 'Case close'),
            ('insurance', 'Insurance approval'),
            ('quote', 'Quotation approval'),
        ],
        required=True,
    )
    min_amount = fields.Monetary(currency_field='currency_id', default=0.0)
    max_amount = fields.Monetary(currency_field='currency_id')
    currency_id = fields.Many2one(related='company_id.currency_id', store=True)
    line_ids = fields.One2many('gara.approval.policy.line', 'policy_id', string='Approval chain')
    approver_group_id = fields.Many2one('res.groups', string='Approver group (legacy)')
    approver_user_id = fields.Many2one('res.users', string='Approver user (legacy)')
    second_approver_group_id = fields.Many2one('res.groups', string='Second approver group (legacy)')
    second_approver_user_id = fields.Many2one('res.users', string='Second approver user (legacy)')

    def _iter_approver_entries(self):
        """Yield (group, user) tuples in approval order. Prefer line_ids; else legacy fields."""
        self.ensure_one()
        if self.line_ids:
            for line in self.line_ids.sorted('sequence'):
                yield line.approver_group_id, line.approver_user_id
            return
        if self.approver_user_id or self.approver_group_id:
            yield self.approver_group_id, self.approver_user_id
        if self.second_approver_user_id or self.second_approver_group_id:
            yield self.second_approver_group_id, self.second_approver_user_id
