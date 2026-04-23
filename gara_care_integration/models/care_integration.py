# -*- coding: utf-8 -*-

import json
import re

import requests

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class GaraCareProvider(models.Model):
    _name = 'gara.care.provider'
    _description = 'Gara Care Provider'
    _order = 'sequence, name'

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    channel = fields.Selection(
        [
            ('sms', 'SMS'),
            ('zalo', 'Zalo'),
            ('phone', 'Phone'),
            ('email', 'Email'),
        ],
        required=True,
        default='sms',
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    endpoint_url = fields.Char()
    api_key = fields.Char(groups='base.group_system')
    auth_header = fields.Char(default='Authorization')
    auth_scheme = fields.Selection(
        [('none', 'None'), ('bearer', 'Bearer'), ('token', 'Token'), ('raw', 'Raw API Key')],
        default='bearer',
        required=True,
    )
    sender_name = fields.Char()
    http_method = fields.Selection([('post', 'POST'), ('get', 'GET')], default='post', required=True)
    timeout = fields.Integer(default=20, required=True)
    payload_template = fields.Text(
        default='{"to": "{phone}", "message": "{message}", "sender": "{sender}"}',
        help='JSON template. Supported placeholders: {phone}, {message}, {sender}, {partner}, {case}, {channel}.',
    )
    success_path = fields.Char(default='success')
    external_ref_path = fields.Char(default='message_id')
    error_path = fields.Char(default='error')
    note = fields.Text()

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Provider code must be unique.'),
    ]

    @api.constrains('payload_template')
    def _check_payload_template(self):
        allowed = _SafeFormat({
            'phone': '',
            'message': '',
            'sender': '',
            'partner': '',
            'case': '',
            'channel': '',
        })
        for provider in self:
            try:
                payload = _render_placeholder_template(provider.payload_template or '{}', allowed)
                json.loads(payload)
            except (KeyError, ValueError, json.JSONDecodeError) as error:
                raise ValidationError(_('Invalid provider payload template: %s') % error) from error

    def _headers(self):
        self.ensure_one()
        headers = {'Content-Type': 'application/json'}
        if self.api_key and self.auth_scheme != 'none':
            if self.auth_scheme == 'bearer':
                value = 'Bearer %s' % self.api_key
            elif self.auth_scheme == 'token':
                value = 'Token %s' % self.api_key
            else:
                value = self.api_key
            headers[self.auth_header or 'Authorization'] = value
        return headers

    def _get_response_value(self, payload, path):
        if not path:
            return False
        value = payload
        for part in path.split('.'):
            if not isinstance(value, dict):
                return False
            value = value.get(part)
        return value

    def _send_message(self, log):
        self.ensure_one()
        if self.channel != log.channel:
            raise UserError(_('Provider channel does not match log channel.'))
        if not self.endpoint_url:
            raise UserError(_('Provider endpoint URL is required.'))
        values = _SafeFormat({
            'phone': log.phone or log.partner_id.mobile or log.partner_id.phone or '',
            'message': log.rendered_body or '',
            'sender': self.sender_name or '',
            'partner': log.partner_id.display_name or '',
            'case': log.case_id.name or '',
            'channel': log.channel or '',
        })
        payload = json.loads(_render_placeholder_template(self.payload_template or '{}', values))
        request_kwargs = {
            'headers': self._headers(),
            'timeout': self.timeout,
        }
        if self.http_method == 'post':
            response = requests.post(self.endpoint_url, json=payload, **request_kwargs)
        else:
            response = requests.get(self.endpoint_url, params=payload, **request_kwargs)
        try:
            response_payload = response.json()
        except ValueError:
            response_payload = {'raw': response.text}
        response.raise_for_status()
        success_value = self._get_response_value(response_payload, self.success_path)
        if self.success_path and success_value in (False, 'false', 'False', 0, '0', None):
            error_value = self._get_response_value(response_payload, self.error_path) or response_payload
            raise UserError(_('Provider returned failure: %s') % error_value)
        return {
            'external_ref': self._get_response_value(response_payload, self.external_ref_path) or False,
            'response_payload': response_payload,
        }


class GaraCareMessageTemplate(models.Model):
    _name = 'gara.care.message.template'
    _description = 'Gara Care Message Template'
    _order = 'channel, sequence, name'

    name = fields.Char(required=True)
    channel = fields.Selection(
        [
            ('sms', 'SMS'),
            ('zalo', 'Zalo'),
            ('phone', 'Phone'),
            ('email', 'Email'),
        ],
        required=True,
        default='sms',
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    subject = fields.Char()
    body = fields.Text(
        required=True,
        help='Supported placeholders: {partner}, {phone}, {case}, {vehicle}.',
    )

    def action_create_log(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Create Care Log'),
            'res_model': 'gara.care.communication.log',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_template_id': self.id,
                'default_channel': self.channel,
                'default_name': self.subject or self.name,
                'default_message_body': self.body,
            },
        }


class GaraCareCommunicationLog(models.Model):
    _name = 'gara.care.communication.log'
    _description = 'Gara Care Communication Log'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'scheduled_date desc, id desc'

    name = fields.Char(required=True, tracking=True)
    partner_id = fields.Many2one('res.partner', required=True, tracking=True, index=True)
    case_id = fields.Many2one('gara.workshop.case', string='Workshop Case', index=True)
    template_id = fields.Many2one('gara.care.message.template')
    provider_id = fields.Many2one(
        'gara.care.provider',
        domain="[('channel', '=', channel)]",
    )
    channel = fields.Selection(
        [
            ('sms', 'SMS'),
            ('zalo', 'Zalo'),
            ('phone', 'Phone'),
            ('email', 'Email'),
        ],
        required=True,
        default='sms',
        tracking=True,
    )
    scheduled_date = fields.Datetime(default=fields.Datetime.now, required=True)
    sent_date = fields.Datetime(readonly=True)
    phone = fields.Char()
    message_body = fields.Text(required=True)
    rendered_body = fields.Text(compute='_compute_rendered_body', store=True)
    external_ref = fields.Char(readonly=True)
    error_message = fields.Text(readonly=True)
    response_payload = fields.Text(readonly=True)
    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('queued', 'Queued'),
            ('sent', 'Sent/Logged'),
            ('failed', 'Failed'),
            ('cancel', 'Cancelled'),
        ],
        default='draft',
        required=True,
        tracking=True,
        index=True,
    )

    @api.onchange('template_id')
    def _onchange_template_id(self):
        for rec in self:
            if rec.template_id:
                rec.channel = rec.template_id.channel
                rec.name = rec.template_id.subject or rec.template_id.name
                rec.message_body = rec.template_id.body

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        for rec in self:
            if rec.partner_id and not rec.phone:
                rec.phone = rec.partner_id.mobile or rec.partner_id.phone

    @api.depends('message_body', 'partner_id', 'phone', 'case_id', 'case_id.vehicle_id')
    def _compute_rendered_body(self):
        for rec in self:
            vehicle = rec.case_id.vehicle_id.display_name if rec.case_id.vehicle_id else ''
            values = {
                'partner': rec.partner_id.display_name or '',
                'phone': rec.phone or rec.partner_id.mobile or rec.partner_id.phone or '',
                'case': rec.case_id.name or '',
                'vehicle': vehicle,
            }
            rec.rendered_body = (rec.message_body or '').format_map(_SafeFormat(values))

    @api.constrains('message_body')
    def _check_message_body_placeholders(self):
        allowed = _SafeFormat({
            'partner': '',
            'phone': '',
            'case': '',
            'vehicle': '',
        })
        for rec in self:
            try:
                (rec.message_body or '').format_map(allowed)
            except (KeyError, ValueError) as error:
                raise ValidationError(_('Unsupported message placeholder: %s') % error) from error

    def action_queue(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Only draft logs can be queued.'))
            rec.state = 'queued'

    def action_send_now(self):
        for rec in self:
            if rec.state not in ('draft', 'queued', 'failed'):
                raise UserError(_('Only draft, queued, or failed logs can be sent.'))
            rec._send_with_provider()

    @api.model
    def _cron_send_queued_messages(self, limit=50):
        logs = self.search([('state', '=', 'queued')], limit=limit, order='scheduled_date, id')
        for log in logs:
            log._send_with_provider()

    def action_mark_sent(self):
        for rec in self:
            if rec.state not in ('draft', 'queued', 'failed'):
                raise UserError(_('Only draft, queued, or failed logs can be marked sent.'))
            rec.write({
                'state': 'sent',
                'sent_date': fields.Datetime.now(),
                'error_message': False,
            })
            rec._create_care_activity('ok')

    def action_mark_failed(self):
        for rec in self:
            rec.write({
                'state': 'failed',
                'error_message': rec.error_message or _('Marked failed manually.'),
            })
            rec._create_care_activity('callback')

    def action_cancel(self):
        self.write({'state': 'cancel'})

    def _send_with_provider(self):
        self.ensure_one()
        if not self.provider_id:
            raise UserError(_('Provider is required to send this message.'))
        if self.channel in ('phone', 'email'):
            raise UserError(_('Automatic sending is only supported for SMS/Zalo providers.'))
        if not (self.phone or self.partner_id.mobile or self.partner_id.phone):
            raise UserError(_('Recipient phone is required.'))
        try:
            result = self.provider_id._send_message(self)
        except Exception as error:
            self.write({
                'state': 'failed',
                'error_message': str(error),
            })
            self._create_care_activity('callback')
            return False
        self.write({
            'state': 'sent',
            'sent_date': fields.Datetime.now(),
            'external_ref': result.get('external_ref'),
            'response_payload': json.dumps(result.get('response_payload'), ensure_ascii=False),
            'error_message': False,
        })
        self._create_care_activity('ok')
        return True

    def _create_care_activity(self, outcome):
        for rec in self:
            self.env['gara.care.activity'].create({
                'name': rec.name,
                'partner_id': rec.partner_id.id,
                'case_id': rec.case_id.id,
                'channel': rec.channel,
                'activity_date': rec.sent_date or fields.Datetime.now(),
                'outcome': outcome,
                'body': rec.rendered_body,
            })


class _SafeFormat(dict):
    def __missing__(self, key):
        raise KeyError(key)


def _render_placeholder_template(template, values):
    allowed_keys = set(values.keys())

    def replace(match):
        key = match.group(1)
        if key not in allowed_keys:
            raise KeyError(key)
        return str(values[key])

    return re.sub(r'\{([a-zA-Z_][a-zA-Z0-9_]*)\}', replace, template or '')
