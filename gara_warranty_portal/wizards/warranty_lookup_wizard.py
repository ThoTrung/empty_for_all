# -*- coding: utf-8 -*-

from odoo import fields, models


class GaraWarrantyLookupWizard(models.TransientModel):
    _name = 'gara.warranty.lookup.wizard'
    _description = 'Warranty lookup wizard'

    query = fields.Char(required=True)
    state = fields.Selection(
        [
            ('all', 'All'),
            ('active', 'Active warranty'),
            ('expired', 'Expired warranty'),
        ],
        default='all',
        required=True,
    )

    def action_lookup(self):
        self.ensure_one()
        query = self.query.strip()
        domain = [
            '|', '|', '|',
            ('name', 'ilike', query),
            ('serial_number', 'ilike', query),
            ('vehicle_id.license_plate', 'ilike', query),
            ('case_id.partner_id.name', 'ilike', query),
        ]
        today = fields.Date.context_today(self)
        if self.state == 'active':
            domain += ['|', ('warranty_end_date', '=', False), ('warranty_end_date', '>=', today)]
        elif self.state == 'expired':
            domain += [('warranty_end_date', '<', today)]
        return {
            'type': 'ir.actions.act_window',
            'name': 'Tra cứu bảo hành',
            'res_model': 'gara.warranty.claim',
            'view_mode': 'tree,form',
            'domain': domain,
        }
