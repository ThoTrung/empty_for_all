# -*- coding: utf-8 -*-

from odoo import fields, models


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    gara_case_id = fields.Many2one(
        'gara.workshop.case',
        string='Gara case',
        index=True,
        ondelete='set null',
    )
