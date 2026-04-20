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
    active = fields.Boolean(default=True)
    note = fields.Text(string="Ghi chú")

    @api.constrains("date_from", "date_to")
    def _check_date_range(self):
        for rec in self:
            if rec.date_from and rec.date_to and rec.date_from > rec.date_to:
                raise ValidationError(_("Ngày bắt đầu phải nhỏ hơn hoặc bằng ngày kết thúc."))
