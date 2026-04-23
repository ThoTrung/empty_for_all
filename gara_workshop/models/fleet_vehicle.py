# -*- coding: utf-8 -*-

from odoo import fields, models


class FleetVehicle(models.Model):
    _inherit = 'fleet.vehicle'

    gara_engine_no = fields.Char(string='Engine number', tracking=True)
    gara_insurance_policy = fields.Char(string='Insurance policy', tracking=True)
    gara_insurance_expiry = fields.Date(string='Insurance expiry', tracking=True)
    gara_registration_expiry = fields.Date(string='Registration expiry', tracking=True)
