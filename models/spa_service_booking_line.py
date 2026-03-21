# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SpaServiceBookingLine(models.Model):
    """Dòng đặt lịch: một dịch vụ con trong đặt lịch tổng (composite). Dùng để check rảnh/capacity theo từng dòng."""
    _name = "spa.service.booking.line"
    _description = "Dòng đặt lịch (dịch vụ con)"
    _order = "sequence, id"

    booking_id = fields.Many2one(
        "spa.service.booking",
        string="Đặt lịch",
        required=True,
        ondelete="cascade",
        index=True,
    )
    product_id = fields.Many2one(
        "product.product",
        string="Dịch vụ",
        required=True,
        domain=[("detailed_type", "=", "service")],
    )
    staff_id = fields.Many2one("res.users", string="Nhân viên", domain=[("share", "=", False)])
    sequence = fields.Integer(string="Thứ tự", default=10)
    duration_minutes = fields.Integer(string="Thời gian (phút)", default=60, required=True)
    start_datetime = fields.Datetime(string="Bắt đầu", required=True)
    end_datetime = fields.Datetime(
        string="Kết thúc",
        compute="_compute_end_datetime",
        store=True,
        readonly=False,
        inverse="_inverse_end_datetime",
    )

    @api.depends("start_datetime", "duration_minutes")
    def _compute_end_datetime(self):
        for rec in self:
            if rec.start_datetime and rec.duration_minutes and rec.duration_minutes > 0:
                rec.end_datetime = rec.start_datetime + timedelta(minutes=rec.duration_minutes)
            else:
                rec.end_datetime = rec.start_datetime

    def _inverse_end_datetime(self):
        for rec in self:
            if rec.start_datetime and rec.end_datetime and rec.end_datetime > rec.start_datetime:
                delta = rec.end_datetime - rec.start_datetime
                rec.duration_minutes = int(round(delta.total_seconds() / 60.0))

    def _get_capacity_percent(self):
        """Phần trăm chiếm dụng NV của dịch vụ này (1-100)."""
        self.ensure_one()
        if not self.product_id:
            return 100
        tmpl = self.product_id.product_tmpl_id
        if hasattr(tmpl, "spa_staff_capacity_percent") and tmpl.spa_staff_capacity_percent:
            return max(1, min(100, tmpl.spa_staff_capacity_percent))
        return 100

    @api.constrains("duration_minutes", "start_datetime", "end_datetime")
    def _check_duration_and_datetime(self):
        for rec in self:
            if rec.duration_minutes is not None and rec.duration_minutes <= 0:
                raise ValidationError(_("Thời gian (phút) phải lớn hơn 0."))
            if rec.start_datetime and rec.end_datetime and rec.end_datetime <= rec.start_datetime:
                raise ValidationError(_("Thời gian kết thúc phải sau thời gian bắt đầu."))
