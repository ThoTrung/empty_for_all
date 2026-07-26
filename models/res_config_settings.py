# -*- coding: utf-8 -*-

import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

HEX_COLOR_RE = re.compile(r"^#?[0-9a-fA-F]{3}([0-9a-fA-F]{3})?$")

DEFAULT_CUSTOMER_REQUESTED_BG = "#FF8C00"
DEFAULT_CUSTOMER_REQUESTED_FG = "#000000"


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    booking_calendar_hex_color_customer_requested = fields.Char(
        string="HEX: Khách chủ động đặt NV",
        default=DEFAULT_CUSTOMER_REQUESTED_BG,
        help="Màu nền HEX trên lịch khi tick «Khách chủ động đặt NV» "
        "(chỉ trạng thái Đặt lịch / Đã xác nhận).",
    )
    booking_calendar_hex_text_color_customer_requested = fields.Char(
        string="HEX chữ: Khách chủ động đặt NV",
        default=DEFAULT_CUSTOMER_REQUESTED_FG,
        help="Màu chữ HEX tương ứng. Để trống sẽ tự chọn trắng/đen theo nền.",
    )

    def get_values(self):
        res = super().get_values()
        ICP = self.env["ir.config_parameter"].sudo()
        bg = self._normalize_hex_color(
            ICP.get_param(
                "spa.booking_calendar_hex_color_customer_requested",
                DEFAULT_CUSTOMER_REQUESTED_BG,
            )
        ) or DEFAULT_CUSTOMER_REQUESTED_BG
        fg_raw = ICP.get_param(
            "spa.booking_calendar_hex_text_color_customer_requested",
            DEFAULT_CUSTOMER_REQUESTED_FG,
        )
        fg = self._normalize_hex_color(fg_raw) or ""
        res["booking_calendar_hex_color_customer_requested"] = bg
        res["booking_calendar_hex_text_color_customer_requested"] = (
            fg or DEFAULT_CUSTOMER_REQUESTED_FG
        )
        return res

    def set_values(self):
        super().set_values()
        ICP = self.env["ir.config_parameter"].sudo()
        ICP.set_param(
            "spa.booking_calendar_hex_color_customer_requested",
            self._normalize_hex_color(self.booking_calendar_hex_color_customer_requested)
            or DEFAULT_CUSTOMER_REQUESTED_BG,
        )
        ICP.set_param(
            "spa.booking_calendar_hex_text_color_customer_requested",
            self._normalize_hex_color(
                self.booking_calendar_hex_text_color_customer_requested
            )
            or "",
        )

    @api.constrains(
        "booking_calendar_hex_color_customer_requested",
        "booking_calendar_hex_text_color_customer_requested",
    )
    def _check_booking_calendar_hex_color_customer_requested(self):
        for rec in self:
            for fname in (
                "booking_calendar_hex_color_customer_requested",
                "booking_calendar_hex_text_color_customer_requested",
            ):
                val = (getattr(rec, fname, "") or "").strip()
                if not val:
                    continue
                if not HEX_COLOR_RE.match(val):
                    raise ValidationError(
                        _(
                            "Màu HEX không hợp lệ tại trường '%s'. "
                            "Ví dụ hợp lệ: #fff, #3A86FF, fff."
                        )
                        % rec._fields[fname].string
                    )
