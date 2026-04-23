# -*- coding: utf-8 -*-

from odoo import api, fields, models


class GaraReminder(models.Model):
    _name = 'gara.reminder'
    _description = 'Vehicle reminder (maintenance/insurance/registration)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'due_date asc, id desc'

    name = fields.Char(required=True, tracking=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    partner_id = fields.Many2one('res.partner', required=True, index=True)
    vehicle_id = fields.Many2one('fleet.vehicle', index=True)
    case_id = fields.Many2one('gara.workshop.case', index=True, ondelete='set null')
    reminder_type = fields.Selection(
        [
            ('maintenance', 'Maintenance'),
            ('insurance', 'Insurance'),
            ('registration', 'Registration'),
            ('other', 'Other'),
        ],
        required=True,
        default='maintenance',
        tracking=True,
    )
    due_date = fields.Date(required=True, tracking=True)
    channel = fields.Selection(
        [('phone', 'Phone'), ('zalo', 'Zalo'), ('sms', 'SMS'), ('email', 'Email')],
        default='phone',
        required=True,
    )
    state = fields.Selection(
        [('pending', 'Pending'), ('done', 'Done'), ('cancel', 'Cancelled')],
        default='pending',
        tracking=True,
        index=True,
    )
    note = fields.Html()

    @api.model
    def cron_mark_overdue_activity(self):
        """Create follow-up activities for pending reminders due today/earlier."""
        today = fields.Date.context_today(self)
        reminders = self.search([('state', '=', 'pending'), ('due_date', '<=', today)])
        todo = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
        if not todo:
            return
        for rec in reminders:
            assignee = False
            if rec.case_id and rec.case_id.user_id:
                assignee = rec.case_id.user_id.id
            elif rec.create_uid:
                assignee = rec.create_uid.id
            rec.activity_schedule(
                activity_type_id=todo.id,
                summary=f'Reminder due: {rec.name}',
                note='Customer reminder follow-up.',
                user_id=assignee,
            )
