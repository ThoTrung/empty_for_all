# -*- coding: utf-8 -*-

from odoo import fields, models, _
from odoo.exceptions import UserError


class GaraWorkAssignment(models.Model):
    _name = 'gara.work.assignment'
    _description = 'Gara work assignment'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'deadline asc, id desc'

    name = fields.Char(required=True, tracking=True)
    case_id = fields.Many2one('gara.workshop.case', required=True, ondelete='cascade', index=True)
    assigned_by_id = fields.Many2one('res.users', default=lambda self: self.env.user, required=True)
    assigned_to_id = fields.Many2one('res.users', required=True, tracking=True)
    deadline = fields.Datetime(tracking=True)
    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('assigned', 'Assigned'),
            ('in_progress', 'In Progress'),
            ('done', 'Done'),
            ('cancel', 'Cancelled'),
        ],
        default='draft',
        tracking=True,
        index=True,
    )
    note = fields.Text()

    def action_assign(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Only draft assignments can be assigned.'))
            rec.state = 'assigned'
            rec._schedule_todo()

    def action_start(self):
        self.write({'state': 'in_progress'})

    def action_done(self):
        self.write({'state': 'done'})

    def action_cancel(self):
        self.write({'state': 'cancel'})

    def _schedule_todo(self):
        todo = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
        if not todo:
            return
        for rec in self:
            rec.activity_schedule(
                activity_type_id=todo.id,
                summary=rec.name,
                note=rec.note or '',
                user_id=rec.assigned_to_id.id,
                date_deadline=fields.Date.to_date(rec.deadline) if rec.deadline else False,
            )
