# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = 'res.partner'

    gara_vn_province_id = fields.Many2one('gara.vn.province', string='Province/City')
    gara_vn_district_id = fields.Many2one(
        'gara.vn.district',
        string='District',
        domain="[('province_id', '=', gara_vn_province_id)]",
    )
    gara_vn_ward_id = fields.Many2one(
        'gara.vn.ward',
        string='Ward',
        domain="[('district_id', '=', gara_vn_district_id)]",
    )

    @api.onchange('gara_vn_province_id')
    def _onchange_gara_vn_province_id(self):
        for partner in self:
            province = partner.gara_vn_province_id
            if partner.gara_vn_district_id.province_id != province:
                partner.gara_vn_district_id = False
                partner.gara_vn_ward_id = False
            if province:
                partner.country_id = province.country_id
                partner.state_id = province.state_id

    @api.onchange('gara_vn_district_id')
    def _onchange_gara_vn_district_id(self):
        for partner in self:
            district = partner.gara_vn_district_id
            if district:
                partner.gara_vn_province_id = district.province_id
                partner.city = district.name
            if partner.gara_vn_ward_id.district_id != district:
                partner.gara_vn_ward_id = False

    @api.onchange('gara_vn_ward_id')
    def _onchange_gara_vn_ward_id(self):
        for partner in self:
            ward = partner.gara_vn_ward_id
            if ward:
                partner.gara_vn_district_id = ward.district_id
                partner.gara_vn_province_id = ward.province_id
                partner.zip = ward.postal_code

    @api.constrains('gara_vn_province_id', 'gara_vn_district_id', 'gara_vn_ward_id')
    def _check_gara_vn_address_hierarchy(self):
        for partner in self:
            if partner.gara_vn_district_id and partner.gara_vn_district_id.province_id != partner.gara_vn_province_id:
                raise ValidationError('District must belong to the selected province/city.')
            if partner.gara_vn_ward_id and partner.gara_vn_ward_id.district_id != partner.gara_vn_district_id:
                raise ValidationError('Ward must belong to the selected district.')
