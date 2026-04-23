# -*- coding: utf-8 -*-

from odoo import fields, models


class GaraWarrantyClaim(models.Model):
    _inherit = 'gara.warranty.claim'

    partner_id = fields.Many2one(
        'res.partner',
        related='case_id.partner_id',
        store=True,
        readonly=True,
    )
    serial_number = fields.Char(index=True)
    warranty_start_date = fields.Date()
    warranty_end_date = fields.Date(index=True)
    lookup_note = fields.Char()
