# -*- coding: utf-8 -*-

from datetime import datetime, time, timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


def _time_from_float(hours_float):
    """Chuyển số giờ (vd. 9.5) thành time(9, 30)."""
    if hours_float is None:
        return time(9, 0)
    h = int(hours_float) % 24
    m = int(round((hours_float % 1) * 60)) % 60
    return time(h, m)


class SpaRecurringBookingWizard(models.TransientModel):
    _name = "spa.recurring.booking.wizard"
    _description = "Đặt lịch theo ngày trong tuần"

    partner_id = fields.Many2one(
        "res.partner",
        string="Khách hàng",
        required=True,
    )
    card_id = fields.Many2one(
        "spa.treatment.card",
        string="Thẻ trị liệu",
        required=True,
        domain="[('partner_id', '=', partner_id), ('available_for_booking', '>', 0), ('state', '=', 'active')]",
    )
    start_date = fields.Date(
        string="Từ ngày",
        required=True,
        default=fields.Date.context_today,
        help="Bắt đầu tạo lịch từ ngày này.",
    )
    start_time_float = fields.Float(
        string="Giờ bắt đầu",
        required=True,
        default=9.0,
        help="Giờ bắt đầu mỗi buổi (áp dụng cho cả chuỗi). Ví dụ: 9 = 9:00, 9.5 = 9:30.",
    )
    # 0=Monday ... 6=Sunday (theo date.weekday())
    mon = fields.Boolean(string="Thứ 2", default=False)
    tue = fields.Boolean(string="Thứ 3", default=False)
    wed = fields.Boolean(string="Thứ 4", default=False)
    thu = fields.Boolean(string="Thứ 5", default=False)
    fri = fields.Boolean(string="Thứ 6", default=False)
    sat = fields.Boolean(string="Thứ 7", default=False)
    sun = fields.Boolean(string="CN", default=False)

    def _get_selected_weekdays(self):
        """Trả về set {0..6} tương ứng thứ 2..CN."""
        self.ensure_one()
        mapping = [
            ("mon", 0),
            ("tue", 1),
            ("wed", 2),
            ("thu", 3),
            ("fri", 4),
            ("sat", 5),
            ("sun", 6),
        ]
        return {wd for fname, wd in mapping if getattr(self, fname)}

    @api.constrains("start_time_float")
    def _check_start_time(self):
        for rec in self:
            if rec.start_time_float is not None and (rec.start_time_float < 0 or rec.start_time_float >= 24):
                raise ValidationError(_("Giờ bắt đầu phải trong khoảng 0–24."))

    def action_create_bookings(self):
        self.ensure_one()
        if not self.card_id:
            raise UserError(_("Vui lòng chọn thẻ trị liệu."))
        n = self.card_id.available_for_booking
        if n <= 0:
            raise UserError(_("Thẻ không còn buổi nào để đặt lịch."))
        weekdays = self._get_selected_weekdays()
        if not weekdays:
            raise UserError(_("Vui lòng chọn ít nhất một ngày trong tuần."))

        t = _time_from_float(self.start_time_float)
        duration = self.card_id.duration_minutes or 60
        Booking = self.env["spa.service.booking"]
        created = []
        # Tối đa 1 năm để tránh lặp vô hạn
        max_days = 366
        day = 0
        current = self.start_date
        while len(created) < n and day < max_days:
            if current.weekday() in weekdays:
                start_dt = datetime.combine(current, t)
                vals = {
                    "partner_id": self.partner_id.id,
                    "card_id": self.card_id.id,
                    "start_datetime": start_dt,
                    "duration": duration,
                    "bed_id": False,
                    "product_id": self.card_id.product_id.id if self.card_id.product_id else False,
                }
                booking = Booking.create(vals)
                created.append(booking)
            current += timedelta(days=1)
            day += 1

        if not created:
            raise UserError(_("Không tạo được buổi nào trong khoảng thời gian cho phép."))

        return {
            "type": "ir.actions.act_window",
            "name": _("Đã tạo %s đặt lịch") % len(created),
            "res_model": "spa.service.booking",
            "view_mode": "tree,form",
            "domain": [("id", "in", [b.id for b in created])],
        }
