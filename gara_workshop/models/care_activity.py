# -*- coding: utf-8 -*-

from odoo import fields, models


class GaraCareActivity(models.Model):
    _name = 'gara.care.activity'
    _description = 'Customer care activity (CSKH)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'activity_date desc, id desc'

    name = fields.Char(string='Subject', required=True, tracking=True)
    partner_id = fields.Many2one(
        'res.partner',
        string='Customer',
        required=True,
        index=True,
    )
    case_id = fields.Many2one(
        'gara.workshop.case',
        string='Related case',
        ondelete='set null',
        index=True,
    )
    channel = fields.Selection(
        selection=[
            ('phone', 'Phone'),
            ('zalo', 'Zalo'),
            ('sms', 'SMS'),
            ('email', 'Email'),
            ('visit', 'Visit'),
            ('other', 'Other'),
        ],
        string='Channel',
        default='phone',
        required=True,
    )
    activity_date = fields.Datetime(
        string='When',
        default=fields.Datetime.now,
        required=True,
    )
    outcome = fields.Selection(
        selection=[
            ('ok', 'Success'),
            ('no_answer', 'No answer'),
            ('callback', 'Callback needed'),
            ('reject', 'Rejected'),
        ],
        string='Outcome',
        default='ok',
    )
    body = fields.Html(string='Details')
