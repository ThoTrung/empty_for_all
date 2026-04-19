# -*- coding: utf-8 -*-

from odoo import fields, models


class RentalTransportMatrixOverlapWizard(models.TransientModel):
    _name = "rental.transport.matrix.overlap.wizard"
    _description = "Rental transport matrix date overlap warning"

    rental_contract_id = fields.Many2one(
        "rental.contract",
        string="Rental contract",
        required=True,
        readonly=True,
    )

    def action_open_transport_matrices(self):
        self.ensure_one()
        return self.rental_contract_id.action_open_transport_matrices()
