# -*- coding: utf-8 -*-

from odoo import fields, models, _


class GaraWorkshopCase(models.Model):
    _inherit = 'gara.workshop.case'

    service_stock_request_ids = fields.One2many(
        'gara.service.stock.request',
        'case_id',
        string='Service Stock Requests',
    )
    service_stock_request_count = fields.Integer(
        compute='_compute_service_stock_request_count',
        string='Stock Requests',
    )

    def _compute_service_stock_request_count(self):
        for case in self:
            case.service_stock_request_count = len(case.service_stock_request_ids)

    def action_view_service_stock_requests(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Service Stock Requests'),
            'res_model': 'gara.service.stock.request',
            'view_mode': 'tree,form',
            'domain': [('case_id', '=', self.id)],
            'context': {'default_case_id': self.id, 'default_company_id': self.company_id.id},
        }
