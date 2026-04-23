# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class GaraCareActivity(models.Model):
    _inherit = 'gara.care.activity'

    care_type_id = fields.Many2one('gara.care.type', string='Care Type')
    result_id = fields.Many2one('gara.care.result', string='Care Result')
    result_detail_id = fields.Many2one(
        'gara.care.result.detail',
        string='Care Result Detail',
        domain="[('result_id', '=', result_id)]",
    )

    @api.onchange('result_id')
    def _onchange_result_id(self):
        for rec in self:
            if rec.result_detail_id and rec.result_detail_id.result_id != rec.result_id:
                rec.result_detail_id = False

    @api.constrains('result_id', 'result_detail_id')
    def _check_result_detail(self):
        for rec in self:
            if rec.result_detail_id and rec.result_detail_id.result_id != rec.result_id:
                raise ValidationError('Care result detail must belong to the selected care result.')
