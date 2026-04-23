# -*- coding: utf-8 -*-

from odoo import fields, models


class GaraVnProvince(models.Model):
    _name = 'gara.vn.province'
    _description = 'Vietnam Province/City'
    _order = 'sequence, name'

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    country_id = fields.Many2one('res.country', default=lambda self: self.env.ref('base.vn'), required=True)
    state_id = fields.Many2one('res.country.state', domain="[('country_id', '=', country_id)]")
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'The province code must be unique.'),
    ]


class GaraVnDistrict(models.Model):
    _name = 'gara.vn.district'
    _description = 'Vietnam District'
    _order = 'province_id, sequence, name'

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    province_id = fields.Many2one('gara.vn.province', required=True, ondelete='cascade')
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('code_province_unique', 'unique(code, province_id)', 'The district code must be unique per province.'),
    ]


class GaraVnWard(models.Model):
    _name = 'gara.vn.ward'
    _description = 'Vietnam Ward'
    _order = 'district_id, sequence, name'

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    district_id = fields.Many2one('gara.vn.district', required=True, ondelete='cascade')
    province_id = fields.Many2one('gara.vn.province', related='district_id.province_id', store=True, readonly=True)
    postal_code = fields.Char()
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('code_district_unique', 'unique(code, district_id)', 'The ward code must be unique per district.'),
    ]
