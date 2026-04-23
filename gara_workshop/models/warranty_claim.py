# -*- coding: utf-8 -*-

from odoo import api, fields, models


class GaraWarrantyClaim(models.Model):
    _name = 'gara.warranty.claim'
    _description = 'Warranty claim'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(string='Reference', required=True, default='New', copy=False)
    company_id = fields.Many2one(
        'res.company',
        default=lambda self: self.env.company,
        required=True,
    )
    case_id = fields.Many2one(
        'gara.workshop.case',
        string='Originating case',
        ondelete='set null',
        index=True,
    )
    vehicle_id = fields.Many2one(
        'fleet.vehicle',
        string='Vehicle',
        index=True,
    )
    product_id = fields.Many2one(
        'product.product',
        string='Part / service',
    )
    description = fields.Text(string='Description')
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('approved', 'Approved'),
            ('in_progress', 'In progress'),
            ('done', 'Done'),
            ('rejected', 'Rejected'),
        ],
        default='draft',
        tracking=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('gara.warranty.claim') or 'New'
        return super().create(vals_list)
