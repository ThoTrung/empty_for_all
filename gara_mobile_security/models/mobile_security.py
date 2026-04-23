# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class GaraMobileRoleFeature(models.Model):
    _name = 'gara.mobile.role.feature'
    _description = 'Gara Mobile Role Feature'
    _order = 'app_scope, sequence, code'

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    group_id = fields.Many2one('res.groups', required=True, ondelete='cascade')
    app_scope = fields.Selection(
        [('mobile', 'Mobile App'), ('web', 'Web'), ('both', 'Both')],
        default='mobile',
        required=True,
    )
    can_read = fields.Boolean(default=True)
    can_create = fields.Boolean()
    can_write = fields.Boolean()
    can_unlink = fields.Boolean()
    active = fields.Boolean(default=True)
    note = fields.Text()

    _sql_constraints = [
        ('code_group_unique', 'unique(code, group_id)', 'The feature code must be unique per role.'),
    ]


class GaraMobileDisplaySetting(models.Model):
    _name = 'gara.mobile.display.setting'
    _description = 'Gara Mobile Display Setting'
    _order = 'model_name, user_id, group_id, sequence, field_name'

    name = fields.Char(compute='_compute_name', store=True)
    model_name = fields.Char(required=True)
    field_name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    user_id = fields.Many2one('res.users', ondelete='cascade')
    group_id = fields.Many2one('res.groups', ondelete='cascade')
    app_scope = fields.Selection(
        [('mobile', 'Mobile App'), ('web', 'Web'), ('both', 'Both')],
        default='mobile',
        required=True,
    )
    visible = fields.Boolean(default=True)
    is_readonly = fields.Boolean(string='Readonly')
    active = fields.Boolean(default=True)
    note = fields.Text()

    @api.depends('model_name', 'field_name', 'user_id.name', 'group_id.name')
    def _compute_name(self):
        for rec in self:
            owner = rec.user_id.name or rec.group_id.name or 'Global'
            rec.name = '%s.%s - %s' % (rec.model_name or '', rec.field_name or '', owner)

    @api.constrains('user_id', 'group_id')
    def _check_owner(self):
        for rec in self:
            if rec.user_id and rec.group_id:
                raise ValidationError('Display setting can target either a user or a group, not both.')

    _sql_constraints = [
        (
            'field_owner_unique',
            'unique(model_name, field_name, user_id, group_id, app_scope)',
            'The field display setting already exists for this scope.',
        ),
    ]


class GaraMobileStatusColor(models.Model):
    _name = 'gara.mobile.status.color'
    _description = 'Gara Mobile Status Color'
    _order = 'model_name, sequence, state_value'

    name = fields.Char(compute='_compute_name', store=True)
    model_name = fields.Char(required=True)
    state_value = fields.Char(required=True)
    label = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    color = fields.Integer(default=0)
    hex_color = fields.Char(default='#6b7280')
    active = fields.Boolean(default=True)
    note = fields.Text()

    @api.depends('model_name', 'state_value', 'label')
    def _compute_name(self):
        for rec in self:
            rec.name = '%s:%s - %s' % (rec.model_name or '', rec.state_value or '', rec.label or '')

    _sql_constraints = [
        ('state_model_unique', 'unique(model_name, state_value)', 'The status color must be unique per model/state.'),
    ]
