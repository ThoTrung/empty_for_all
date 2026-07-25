# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from odoo.addons.rental.services import rental_contract_services as rcs


class RentalRentedQtyWizard(models.TransientModel):
    _name = "rental.rented.qty.wizard"
    _description = "Số lượng đang thuê theo ngày"

    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        readonly=True,
    )
    as_of_date = fields.Date(
        string="Ngày tra cứu",
        required=True,
        default=fields.Date.context_today,
    )
    partner_company_id = fields.Many2one(
        "res.partner",
        string="Khách hàng",
        domain="[('is_company', '=', True), "
               "('customer_type', '=', 'renter'), "
               "('company_id', '=', company_id)]",
    )
    rental_contract_id = fields.Many2one(
        "rental.contract",
        string="Hợp đồng",
        domain="[('company_id', '=', company_id), "
               "('a_company_party', '=?', partner_company_id)]",
    )
    product_tmpl_id = fields.Many2one(
        "product.template",
        string="Sản phẩm",
    )
    only_active_contracts = fields.Boolean(
        string="Chỉ hợp đồng đang hiệu lực",
        default=True,
    )
    line_ids = fields.One2many(
        "rental.rented.qty.wizard.line",
        "wizard_id",
        string="Số lượng đang thuê",
        readonly=True,
    )

    @api.constrains("partner_company_id", "company_id")
    def _check_partner_company_scope(self):
        for wizard in self.filtered("partner_company_id"):
            partner = wizard.partner_company_id
            if (
                not partner.is_company
                or partner.customer_type != "renter"
                or partner.company_id != wizard.company_id
            ):
                raise ValidationError(_(
                    "Khách hàng phải là công ty có loại Khách thuê và thuộc "
                    "đúng công ty hiện tại."
                ))

    @api.onchange("partner_company_id")
    def _onchange_partner_company_id(self):
        if (
            self.rental_contract_id
            and self.rental_contract_id.a_company_party != self.partner_company_id
        ):
            self.rental_contract_id = False

    @api.onchange("rental_contract_id")
    def _onchange_rental_contract_id(self):
        if self.rental_contract_id:
            self.partner_company_id = self.rental_contract_id.a_company_party
            self.company_id = self.rental_contract_id.company_id

    def action_compute(self):
        self.ensure_one()
        rows = rcs.calc_rented_qty_as_of(
            self.env,
            self.as_of_date,
            contract_ids=(
                self.rental_contract_id.ids
                if self.rental_contract_id
                else None
            ),
            partner_company_ids=(
                self.partner_company_id.ids
                if self.partner_company_id
                else None
            ),
            tmpl_ids=self.product_tmpl_id.ids if self.product_tmpl_id else None,
            only_active_contracts=(
                self.only_active_contracts and not self.rental_contract_id
            ),
        )
        self.line_ids = [(5, 0, 0)] + [
            (0, 0, {
                "company_id": self.company_id.id,
                "partner_company_id": row["partner_company_id"],
                "rental_contract_id": row["contract_id"],
                "product_tmpl_id": row["tmpl_id"],
                "uom_name": row["uom_name"],
                "rented_qty": row["rented_qty"],
                "excess_qty": row["excess_qty"],
                "physical_qty": row["physical_qty"],
            })
            for row in rows
        ]
        return {
            "type": "ir.actions.act_window",
            "name": "SL đang thuê theo ngày",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }


class RentalRentedQtyWizardLine(models.TransientModel):
    _name = "rental.rented.qty.wizard.line"
    _description = "Kết quả số lượng đang thuê theo ngày"
    _order = "partner_company_id, rental_contract_id, product_tmpl_id"

    wizard_id = fields.Many2one(
        "rental.rented.qty.wizard",
        required=True,
        ondelete="cascade",
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        readonly=True,
        index=True,
    )
    partner_company_id = fields.Many2one(
        "res.partner",
        string="Khách hàng",
        required=True,
        readonly=True,
    )
    rental_contract_id = fields.Many2one(
        "rental.contract",
        string="Hợp đồng",
        required=True,
        readonly=True,
    )
    product_tmpl_id = fields.Many2one(
        "product.template",
        string="Sản phẩm",
        required=True,
        readonly=True,
    )
    uom_name = fields.Char(string="ĐVT", readonly=True)
    rented_qty = fields.Float(
        string="SL đang thuê",
        digits="Product Unit of Measure",
        readonly=True,
    )
    excess_qty = fields.Float(
        string="SL chuyển thừa",
        digits="Product Unit of Measure",
        readonly=True,
    )
    physical_qty = fields.Float(
        string="SL vật lý tại KH",
        digits="Product Unit of Measure",
        readonly=True,
    )
