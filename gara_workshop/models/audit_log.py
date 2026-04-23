# -*- coding: utf-8 -*-

from odoo import api, fields, models


class GaraAuditLog(models.Model):
    _name = 'gara.audit.log'
    _description = 'Gara audit log'
    _order = 'create_date desc, id desc'

    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    user_id = fields.Many2one('res.users', required=True, default=lambda self: self.env.user)
    case_id = fields.Many2one('gara.workshop.case', index=True, ondelete='cascade')
    action = fields.Char(required=True, index=True)
    model_name = fields.Char(index=True)
    res_id = fields.Integer(index=True)
    event_type = fields.Selection(
        [('user', 'User Action'), ('system', 'System Action')],
        default='user',
        required=True,
    )
    detail = fields.Text()

    @api.model
    def log_event(
        self,
        *,
        action,
        model_name,
        res_id,
        company_id=False,
        case_id=False,
        detail='',
        event_type='user',
        user_id=False,
    ):
        """Centralized logger for user/system audit events.

        Uses sudo so business flows are never blocked by audit ACLs.
        """
        vals = {
            'action': action,
            'model_name': model_name,
            'res_id': res_id,
            'detail': detail or '',
            'event_type': event_type or 'user',
            'company_id': company_id or self.env.company.id,
            'user_id': user_id or self.env.user.id,
        }
        if case_id:
            vals['case_id'] = case_id
        return self.sudo().create(vals)
