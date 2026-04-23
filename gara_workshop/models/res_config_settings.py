# -*- coding: utf-8 -*-

from odoo import fields, models, _


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    gara_close_approval_threshold = fields.Monetary(
        related='company_id.gara_close_approval_threshold',
        readonly=False,
        currency_field='currency_id',
    )
    gara_insurance_approval_threshold = fields.Monetary(
        related='company_id.gara_insurance_approval_threshold',
        readonly=False,
        currency_field='currency_id',
    )
    gara_quote_require_approval = fields.Boolean(
        related='company_id.gara_quote_require_approval',
        readonly=False,
    )
    gara_member_point_rate = fields.Float(
        related='company_id.gara_member_point_rate',
        readonly=False,
    )

    def action_gara_apply_vn_product_accounts(self):
        self.ensure_one()
        self.company_id.gara_apply_vn_product_account_defaults()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Vietnam accounts'),
                'message': _('Gara default products were updated for this company (if the Vietnam chart is installed).'),
                'sticky': False,
                'type': 'success',
            },
        }
