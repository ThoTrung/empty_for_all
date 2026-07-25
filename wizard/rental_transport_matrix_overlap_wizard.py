# -*- coding: utf-8 -*-

from odoo import fields, models


class RentalTransportMatrixOverlapWizard(models.TransientModel):
    _name = "rental.transport.matrix.overlap.wizard"
    _description = "Cảnh báo trùng ngày bảng xác nhận KL"

    rental_contract_id = fields.Many2one(
        "rental.contract",
        string="Hợp đồng thuê",
        required=True,
        readonly=True,
    )

    def action_open_transport_matrices(self):
        self.ensure_one()
        return self.rental_contract_id.action_open_transport_matrices()
