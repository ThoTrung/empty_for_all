# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SpaStaffDayoff(models.Model):
    _name = "spa.staff.dayoff"
    _description = "Ngày nghỉ nhân viên"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date_start desc, id desc"

    name = fields.Char(string="Mô tả", required=True, tracking=True)
    employee_id = fields.Many2one(
        "hr.employee",
        string="Nhân viên",
        required=True,
        ondelete="cascade",
        tracking=True,
        index=True,
    )
    date_start = fields.Date(string="Từ ngày", required=True, tracking=True)
    date_end = fields.Date(string="Đến ngày", required=True, tracking=True)
    dayoff_type = fields.Selection(
        [
            ("annual", "Nghỉ phép"),
            ("sick", "Ốm"),
            ("unpaid", "Không lương"),
            ("other", "Khác"),
        ],
        string="Loại",
        default="annual",
        tracking=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Công ty",
        related="employee_id.company_id",
        store=True,
        readonly=True,
    )
    note = fields.Text(string="Ghi chú")

    @api.constrains("date_start", "date_end")
    def _check_dates(self):
        for rec in self:
            if rec.date_end and rec.date_start and rec.date_end < rec.date_start:
                raise ValidationError(_("Ngày kết thúc không được trước ngày bắt đầu."))
