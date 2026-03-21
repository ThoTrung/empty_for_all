# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

CALENDAR_COLOR_COUNT = 56


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    booking_reminder_hours_before = fields.Float(
        string="Nhắc lịch trước (giờ)",
        default=2.0,
        config_parameter="spa.booking_reminder_hours_before",
        help="Gửi thông báo cho nhân viên trước X giờ khi có lịch sắp tới (2–3 giờ).",
    )

    spa_calendar_min_time = fields.Char(
        string="Lịch đặt: giờ bắt đầu hiển thị",
        default="05:00:00",
        config_parameter="spa.calendar_min_time",
        help="Chỉ hiển thị từ giờ này (ví dụ 05:00:00). Ẩn 22h–5h sáng.",
    )
    spa_calendar_max_time = fields.Char(
        string="Lịch đặt: giờ kết thúc hiển thị",
        default="22:00:00",
        config_parameter="spa.calendar_max_time",
        help="Chỉ hiển thị đến giờ này (ví dụ 22:00:00).",
    )
    spa_calendar_pixels_per_hour = fields.Integer(
        string="Lịch đặt: độ cao mỗi giờ (px)",
        default=80,
        config_parameter="spa.calendar_pixels_per_hour",
        help="Chiều cao (pixel) của mỗi ô 1 giờ trên lịch. Càng lớn càng dễ đọc (vd. 60, 80, 100).",
    )

    booking_calendar_color_draft = fields.Integer(
        string="Màu: Đặt lịch",
        default=0,
        help="Chỉ số màu (0–55) cho lịch trạng thái Đặt lịch.",
    )
    booking_calendar_color_confirmed = fields.Integer(
        string="Màu: Đã xác nhận",
        default=3,
        help="Chỉ số màu (0–55) cho lịch trạng thái Đã xác nhận.",
    )
    booking_calendar_color_doing = fields.Integer(
        string="Màu: Đang phục vụ",
        default=20,
        help="Chỉ số màu (0–55) cho lịch trạng thái Đang phục vụ.",
    )
    booking_calendar_color_done = fields.Integer(
        string="Màu: Đã hoàn thành",
        default=8,
        help="Chỉ số màu (0–55) cho lịch trạng thái Đã hoàn thành.",
    )
    booking_calendar_color_cancel = fields.Integer(
        string="Màu: Đã hủy",
        default=1,
        help="Chỉ số màu (0–55) cho lịch trạng thái Đã hủy.",
    )

    def get_values(self):
        res = super().get_values()
        ICP = self.env["ir.config_parameter"].sudo()
        keys = [
            ("booking_calendar_color_draft", "spa.booking_calendar_color_draft", 1),
            ("booking_calendar_color_confirmed", "spa.booking_calendar_color_confirmed", 2),
            ("booking_calendar_color_doing", "spa.booking_calendar_color_doing", 3),
            ("booking_calendar_color_done", "spa.booking_calendar_color_done", 4),
            ("booking_calendar_color_cancel", "spa.booking_calendar_color_cancel", 0),
        ]
        for fname, key, default in keys:
            try:
                res[fname] = int(ICP.get_param(key, str(default)))
            except (TypeError, ValueError):
                res[fname] = default
            res[fname] = max(0, min(55, res[fname]))
        return res

    def set_values(self):
        super().set_values()
        ICP = self.env["ir.config_parameter"].sudo()
        ICP.set_param("spa.booking_calendar_color_draft", str(self.booking_calendar_color_draft))
        ICP.set_param("spa.booking_calendar_color_confirmed", str(self.booking_calendar_color_confirmed))
        ICP.set_param("spa.booking_calendar_color_doing", str(self.booking_calendar_color_doing))
        ICP.set_param("spa.booking_calendar_color_done", str(self.booking_calendar_color_done))
        ICP.set_param("spa.booking_calendar_color_cancel", str(self.booking_calendar_color_cancel))

    @api.constrains(
        "booking_calendar_color_draft",
        "booking_calendar_color_confirmed",
        "booking_calendar_color_doing",
        "booking_calendar_color_done",
        "booking_calendar_color_cancel",
    )
    def _check_booking_calendar_colors(self):
        for rec in self:
            for fname in [
                "booking_calendar_color_draft",
                "booking_calendar_color_confirmed",
                "booking_calendar_color_doing",
                "booking_calendar_color_done",
                "booking_calendar_color_cancel",
            ]:
                val = getattr(rec, fname, None)
                if val is not False and val is not None and (val < 0 or val >= CALENDAR_COLOR_COUNT):
                    raise ValidationError(
                        _("Màu lịch đặt lịch phải từ 0 đến %s.") % (CALENDAR_COLOR_COUNT - 1)
                    )
