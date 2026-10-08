# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class SubrentDirectDeliveryWizard(models.TransientModel):
    _name = "rental.subrent.direct.delivery.wizard"
    _description = "Tạo lô giao thẳng NCC → công trình"

    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    subrent_contract_id = fields.Many2one(
        "rental.subrent.contract",
        string="HĐ thuê ngoài",
        required=True,
        domain="[('state', '=', 'active')]",
    )
    product_id = fields.Many2one("product.product", string="Sản phẩm", required=True)
    qty = fields.Float(string="Số lượng", required=True, default=1.0)
    date = fields.Date(required=True, default=fields.Date.context_today)
    lot_id = fields.Many2one("rental.subrent.lot", readonly=True)

    def action_create_lot(self):
        self.ensure_one()
        if self.qty <= 0:
            raise ValidationError(_("Số lượng phải > 0."))
        contract = self.subrent_contract_id
        if contract.state != "active":
            raise UserError(_("HĐ phải đang hiệu lực."))
        line = contract.line_ids.filtered(
            lambda l: l.product_tmpl_id == self.product_id.product_tmpl_id
        )[:1]
        if not line:
            raise ValidationError(
                _("Sản phẩm không có trên HĐ %(c)s.") % {"c": contract.name}
            )
        lot = self.env["rental.subrent.lot"].create({
            "subrent_contract_id": contract.id,
            "product_id": self.product_id.id,
            "stock_flow": "pass_through",
            "cost_unit": line.cost_unit,
            "minimum_rental_months": line.minimum_rental_months,
            "date_start": self.date,
            "date_expected_return": contract.date_end,
            "company_id": self.company_id.id,
        })
        self.lot_id = lot.id
        return {
            "type": "ir.actions.act_window",
            "name": _("Lô giao thẳng"),
            "res_model": "rental.subrent.lot",
            "res_id": lot.id,
            "view_mode": "form",
            "target": "current",
            "context": {
                "default_source_type": "subrent",
                "default_subrent_lot_id": lot.id,
            },
        }
