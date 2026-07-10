# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class RentalHoliday(models.Model):
    _name = "rental.holiday"
    _description = "Rental Holiday Range"
    _order = "date_from desc, id desc"

    name = fields.Char(string="Tên kỳ nghỉ", required=True, tracking=True)
    date_from = fields.Date(string="Từ ngày", required=True, tracking=True)
    date_to = fields.Date(string="Đến ngày", required=True, tracking=True)
    company_id = fields.Many2one(
        "res.company",
        string="Công ty",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    rental_contract_id = fields.Many2one(
        "rental.contract",
        string="Hợp đồng",
        index=True,
        ondelete="cascade",
        help="Để trống = ngày nghỉ áp dụng toàn hệ thống (theo công ty). "
             "Nếu chọn hợp đồng, ngày nghỉ chỉ áp dụng riêng cho hợp đồng đó.",
    )
    active = fields.Boolean(default=True)
    note = fields.Text(string="Ghi chú")

    @api.onchange("rental_contract_id")
    def _onchange_rental_contract_id(self):
        for rec in self:
            if rec.rental_contract_id:
                rec.company_id = rec.rental_contract_id.company_id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            contract_id = vals.get("rental_contract_id")
            if contract_id and not vals.get("company_id"):
                contract = self.env["rental.contract"].browse(contract_id)
                if contract.company_id:
                    vals["company_id"] = contract.company_id.id
        return super().create(vals_list)

    @api.constrains("date_from", "date_to")
    def _check_date_range(self):
        for rec in self:
            if rec.date_from and rec.date_to and rec.date_from > rec.date_to:
                raise ValidationError(_("Ngày bắt đầu phải nhỏ hơn hoặc bằng ngày kết thúc."))
