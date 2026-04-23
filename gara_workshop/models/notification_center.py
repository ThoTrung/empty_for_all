# -*- coding: utf-8 -*-

from odoo import api, fields, models


class GaraNotification(models.Model):
    _name = 'gara.notification'
    _description = 'Gara notification center'
    _order = 'priority desc, date desc, id desc'

    name = fields.Char(required=True)
    notification_type = fields.Selection(
        [
            ('reminder', 'Reminder'),
            ('approval', 'Approval'),
            ('assignment', 'Assignment'),
            ('debt', 'Debt'),
            ('stock', 'Stock'),
            ('other', 'Other'),
        ],
        required=True,
        default='other',
        index=True,
    )
    date = fields.Datetime(default=fields.Datetime.now, required=True)
    priority = fields.Selection(
        [('0', 'Low'), ('1', 'Normal'), ('2', 'High')],
        default='1',
        required=True,
    )
    user_id = fields.Many2one('res.users', default=lambda self: self.env.user, index=True)
    partner_id = fields.Many2one('res.partner')
    case_id = fields.Many2one('gara.workshop.case')
    model = fields.Char()
    res_id = fields.Integer()
    state = fields.Selection([('open', 'Open'), ('done', 'Done')], default='open', index=True)
    note = fields.Text()

    def action_done(self):
        self.write({'state': 'done'})

    def action_open_record(self):
        self.ensure_one()
        if not self.model or not self.res_id:
            return False
        return {
            'type': 'ir.actions.act_window',
            'name': self.name,
            'res_model': self.model,
            'res_id': self.res_id,
            'view_mode': 'form',
        }

    @api.model
    def action_generate_notifications(self):
        today = fields.Date.context_today(self)
        self._generate_reminder_notifications(today)
        self._generate_approval_notifications()
        self._generate_assignment_notifications()
        self._generate_debt_notifications()

    @api.model
    def _upsert_notification(self, vals):
        existing = self.search([
            ('model', '=', vals.get('model')),
            ('res_id', '=', vals.get('res_id')),
            ('notification_type', '=', vals.get('notification_type')),
            ('state', '=', 'open'),
        ], limit=1)
        if existing:
            existing.write(vals)
            return existing
        return self.create(vals)

    def _generate_reminder_notifications(self, today):
        reminders = self.env['gara.reminder'].search([
            ('state', '=', 'pending'),
            ('due_date', '<=', today),
        ])
        for rec in reminders:
            self._upsert_notification({
                'name': rec.name,
                'notification_type': 'reminder',
                'priority': '2',
                'user_id': rec.case_id.user_id.id or rec.create_uid.id,
                'partner_id': rec.partner_id.id,
                'case_id': rec.case_id.id,
                'model': rec._name,
                'res_id': rec.id,
                'note': rec.note or '',
            })

    def _generate_approval_notifications(self):
        approvals = self.env['gara.approval.request'].search([('state', '=', 'submitted')])
        for rec in approvals:
            self._upsert_notification({
                'name': rec.name,
                'notification_type': 'approval',
                'priority': '2',
                'user_id': rec.approver_id.id or rec.requester_id.id,
                'case_id': rec.case_id.id,
                'model': rec._name,
                'res_id': rec.id,
                'note': rec.reason or '',
            })

    def _generate_assignment_notifications(self):
        assignments = self.env['gara.work.assignment'].search([
            ('state', 'in', ('assigned', 'in_progress')),
        ])
        for rec in assignments:
            self._upsert_notification({
                'name': rec.name,
                'notification_type': 'assignment',
                'priority': '1',
                'user_id': rec.assigned_to_id.id,
                'case_id': rec.case_id.id,
                'partner_id': rec.case_id.partner_id.id,
                'model': rec._name,
                'res_id': rec.id,
                'note': rec.note or '',
            })

    def _generate_debt_notifications(self):
        cases = self.env['gara.workshop.case'].search([
            ('state', 'not in', ('closed', 'cancel')),
        ]).filtered(lambda case: case.amount_due_estimate > 0.0)
        for rec in cases:
            self._upsert_notification({
                'name': 'Outstanding balance: %s' % rec.name,
                'notification_type': 'debt',
                'priority': '1',
                'user_id': rec.user_id.id,
                'case_id': rec.id,
                'partner_id': rec.partner_id.id,
                'model': rec._name,
                'res_id': rec.id,
                'note': str(rec.amount_due_estimate),
            })
