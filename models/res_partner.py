# -*- coding: utf-8 -*-
from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    subrent_contract_ids = fields.One2many(
        "rental.subrent.contract",
        "supplier_id",
        string="Hợp đồng với NCC",
    )
