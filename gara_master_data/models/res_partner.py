# -*- coding: utf-8 -*-

from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    gara_membership_type_id = fields.Many2one('gara.membership.type', string='Membership Type')
    gara_customer_source_id = fields.Many2one('gara.customer.source', string='Customer Source')
    gara_customer_status_id = fields.Many2one('gara.customer.status', string='Customer Status')
    gara_customer_type_id = fields.Many2one('gara.customer.type', string='Customer Type')
