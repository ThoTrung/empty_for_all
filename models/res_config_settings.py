# -*- coding: utf-8 -*-

import re

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

HEX_COLOR_RE = re.compile(r"^#?[0-9a-fA-F]{3}([0-9a-fA-F]{3})?$")


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

    booking_calendar_hex_color_draft = fields.Char(
        string="HEX: Đặt lịch",
        default="#5e5ce6",
        help="Mã màu HEX cho trạng thái Đặt lịch (vd: #fff, #3A86FF).",
    )
    booking_calendar_hex_color_confirmed = fields.Char(
        string="HEX: Đã xác nhận",
        default="#2a9d8f",
        help="Mã màu HEX cho trạng thái Đã xác nhận (vd: #fff, #3A86FF).",
    )
    booking_calendar_hex_color_doing = fields.Char(
        string="HEX: Đang phục vụ",
        default="#f4a261",
        help="Mã màu HEX cho trạng thái Đang phục vụ (vd: #fff, #3A86FF).",
    )
    booking_calendar_hex_color_done = fields.Char(
        string="HEX: Đã hoàn thành",
        default="#457b9d",
        help="Mã màu HEX cho trạng thái Đã hoàn thành (vd: #fff, #3A86FF).",
    )
    booking_calendar_hex_color_cancel = fields.Char(
        string="HEX: Đã hủy",
        default="#e63946",
        help="Mã màu HEX cho trạng thái Đã hủy (vd: #fff, #3A86FF).",
    )
    booking_calendar_hex_text_color_draft = fields.Char(
        string="HEX chữ: Đặt lịch",
        default="#FFFFFF",
        help="Mã màu chữ HEX cho trạng thái Đặt lịch (vd: #fff hoặc #000).",
    )
    booking_calendar_hex_text_color_confirmed = fields.Char(
        string="HEX chữ: Đã xác nhận",
        default="#000000",
        help="Mã màu chữ HEX cho trạng thái Đã xác nhận (vd: #fff hoặc #000).",
    )
    booking_calendar_hex_text_color_doing = fields.Char(
        string="HEX chữ: Đang phục vụ",
        default="#000000",
        help="Mã màu chữ HEX cho trạng thái Đang phục vụ (vd: #fff hoặc #000).",
    )
    booking_calendar_hex_text_color_done = fields.Char(
        string="HEX chữ: Đã hoàn thành",
        default="#FFFFFF",
        help="Mã màu chữ HEX cho trạng thái Đã hoàn thành (vd: #fff hoặc #000).",
    )
    booking_calendar_hex_text_color_cancel = fields.Char(
        string="HEX chữ: Đã hủy",
        default="#FFFFFF",
        help="Mã màu chữ HEX cho trạng thái Đã hủy (vd: #fff hoặc #000).",
    )

    # --- Màu đặc biệt (chỉ áp dụng cho trạng thái Đặt lịch / draft) ---
    booking_calendar_hex_color_draft_weekly = fields.Char(
        string="Draft: Lịch cố định hàng tuần",
        default="#3E51BA",
        help="Màu nền HEX cho lịch tạo bằng tính năng «Đặt theo tuần» (chỉ trạng thái Đặt lịch).",
    )
    booking_calendar_hex_color_draft_past_created = fields.Char(
        string="Draft: Khách mới đặt (ngày tạo quá khứ)",
        default="#33B577",
        help="Màu nền HEX khi create_date của booking là ngày quá khứ (khác hôm nay) (chỉ trạng thái Đặt lịch).",
    )
    booking_calendar_hex_color_draft_non_session = fields.Char(
        string="Draft: Họp/đào tạo/mẫu (Không trừ buổi)",
        default="#D71629",
        help="Màu nền HEX cho booking_kind=non_session (chỉ trạng thái Đặt lịch).",
    )
    booking_calendar_hex_color_draft_hair_removal = fields.Char(
        string="Draft: Triệt lông",
        default="#F44F15",
        help="Màu nền HEX cho dịch vụ triệt lông (product.template.spa_booking_is_hair_removal) (chỉ trạng thái Đặt lịch).",
    )
    booking_calendar_hex_color_draft_expert_only = fields.Char(
        string="Draft: Dịch vụ chuyên gia",
        default="#8E24AC",
        help="Màu nền HEX cho dịch vụ yêu cầu cấp độ nhân viên = Chuyên gia (chỉ trạng thái Đặt lịch).",
    )
    booking_calendar_hex_text_color_draft_weekly = fields.Char(
        string="Draft chữ: Lịch cố định hàng tuần",
        default="",
        help="Màu chữ HEX (tùy chọn). Nếu để trống sẽ tự chọn trắng/đen theo nền.",
    )
    booking_calendar_hex_text_color_draft_past_created = fields.Char(
        string="Draft chữ: Khách mới đặt (ngày tạo quá khứ)",
        default="",
        help="Màu chữ HEX (tùy chọn). Nếu để trống sẽ tự chọn trắng/đen theo nền.",
    )
    booking_calendar_hex_text_color_draft_non_session = fields.Char(
        string="Draft chữ: Họp/đào tạo/mẫu (Không trừ buổi)",
        default="",
        help="Màu chữ HEX (tùy chọn). Nếu để trống sẽ tự chọn trắng/đen theo nền.",
    )
    booking_calendar_hex_text_color_draft_hair_removal = fields.Char(
        string="Draft chữ: Triệt lông",
        default="",
        help="Màu chữ HEX (tùy chọn). Nếu để trống sẽ tự chọn trắng/đen theo nền.",
    )
    booking_calendar_hex_text_color_draft_expert_only = fields.Char(
        string="Draft chữ: Dịch vụ chuyên gia",
        default="",
        help="Màu chữ HEX (tùy chọn). Nếu để trống sẽ tự chọn trắng/đen theo nền.",
    )
    booking_calendar_hair_removal_category_id = fields.Many2one(
        "product.category",
        string="Danh mục: Triệt lông",
        help="Mọi dịch vụ thuộc danh mục này (và danh mục con) sẽ được coi là «Triệt lông» để áp màu đặc biệt (chỉ trạng thái Đặt lịch).",
    )

    @api.model
    def _normalize_hex_color(self, value):
        val = (value or "").strip()
        if not val:
            return ""
        if not HEX_COLOR_RE.match(val):
            return ""
        return val if val.startswith("#") else f"#{val}"

    def get_values(self):
        res = super().get_values()
        ICP = self.env["ir.config_parameter"].sudo()
        hex_keys = [
            ("booking_calendar_hex_color_draft", "spa.booking_calendar_hex_color_draft", "#5e5ce6"),
            ("booking_calendar_hex_color_confirmed", "spa.booking_calendar_hex_color_confirmed", "#2a9d8f"),
            ("booking_calendar_hex_color_doing", "spa.booking_calendar_hex_color_doing", "#f4a261"),
            ("booking_calendar_hex_color_done", "spa.booking_calendar_hex_color_done", "#457b9d"),
            ("booking_calendar_hex_color_cancel", "spa.booking_calendar_hex_color_cancel", "#e63946"),
        ]
        for fname, key, default in hex_keys:
            raw_val = ICP.get_param(key, default)
            res[fname] = self._normalize_hex_color(raw_val) or default
        text_hex_keys = [
            ("booking_calendar_hex_text_color_draft", "spa.booking_calendar_hex_text_color_draft", "#FFFFFF"),
            ("booking_calendar_hex_text_color_confirmed", "spa.booking_calendar_hex_text_color_confirmed", "#000000"),
            ("booking_calendar_hex_text_color_doing", "spa.booking_calendar_hex_text_color_doing", "#000000"),
            ("booking_calendar_hex_text_color_done", "spa.booking_calendar_hex_text_color_done", "#FFFFFF"),
            ("booking_calendar_hex_text_color_cancel", "spa.booking_calendar_hex_text_color_cancel", "#FFFFFF"),
        ]
        for fname, key, default in text_hex_keys:
            raw_val = ICP.get_param(key, default)
            res[fname] = self._normalize_hex_color(raw_val) or default
        draft_special_keys = [
            ("booking_calendar_hex_color_draft_weekly", "spa.booking_calendar_hex_color_draft_weekly", "#3E51BA"),
            ("booking_calendar_hex_color_draft_past_created", "spa.booking_calendar_hex_color_draft_past_created", "#33B577"),
            ("booking_calendar_hex_color_draft_non_session", "spa.booking_calendar_hex_color_draft_non_session", "#D71629"),
            ("booking_calendar_hex_color_draft_hair_removal", "spa.booking_calendar_hex_color_draft_hair_removal", "#F44F15"),
            ("booking_calendar_hex_color_draft_expert_only", "spa.booking_calendar_hex_color_draft_expert_only", "#8E24AC"),
        ]
        for fname, key, default in draft_special_keys:
            raw_val = ICP.get_param(key, default)
            res[fname] = self._normalize_hex_color(raw_val) or default
        draft_special_text_keys = [
            ("booking_calendar_hex_text_color_draft_weekly", "spa.booking_calendar_hex_text_color_draft_weekly", ""),
            ("booking_calendar_hex_text_color_draft_past_created", "spa.booking_calendar_hex_text_color_draft_past_created", ""),
            ("booking_calendar_hex_text_color_draft_non_session", "spa.booking_calendar_hex_text_color_draft_non_session", ""),
            ("booking_calendar_hex_text_color_draft_hair_removal", "spa.booking_calendar_hex_text_color_draft_hair_removal", ""),
            ("booking_calendar_hex_text_color_draft_expert_only", "spa.booking_calendar_hex_text_color_draft_expert_only", ""),
        ]
        for fname, key, default in draft_special_text_keys:
            raw_val = ICP.get_param(key, default)
            res[fname] = self._normalize_hex_color(raw_val) or default
        try:
            cid = int(ICP.get_param("spa.booking_calendar_hair_removal_category_id", "0") or "0")
        except (TypeError, ValueError):
            cid = 0
        res["booking_calendar_hair_removal_category_id"] = cid or False
        return res

    def set_values(self):
        super().set_values()
        ICP = self.env["ir.config_parameter"].sudo()
        ICP.set_param(
            "spa.booking_calendar_hex_color_draft",
            self._normalize_hex_color(self.booking_calendar_hex_color_draft) or "",
        )
        ICP.set_param(
            "spa.booking_calendar_hex_color_confirmed",
            self._normalize_hex_color(self.booking_calendar_hex_color_confirmed) or "",
        )
        ICP.set_param(
            "spa.booking_calendar_hex_color_doing",
            self._normalize_hex_color(self.booking_calendar_hex_color_doing) or "",
        )
        ICP.set_param(
            "spa.booking_calendar_hex_color_done",
            self._normalize_hex_color(self.booking_calendar_hex_color_done) or "",
        )
        ICP.set_param(
            "spa.booking_calendar_hex_color_cancel",
            self._normalize_hex_color(self.booking_calendar_hex_color_cancel) or "",
        )
        ICP.set_param(
            "spa.booking_calendar_hex_text_color_draft",
            self._normalize_hex_color(self.booking_calendar_hex_text_color_draft) or "",
        )
        ICP.set_param(
            "spa.booking_calendar_hex_text_color_confirmed",
            self._normalize_hex_color(self.booking_calendar_hex_text_color_confirmed) or "",
        )
        ICP.set_param(
            "spa.booking_calendar_hex_text_color_doing",
            self._normalize_hex_color(self.booking_calendar_hex_text_color_doing) or "",
        )
        ICP.set_param(
            "spa.booking_calendar_hex_text_color_done",
            self._normalize_hex_color(self.booking_calendar_hex_text_color_done) or "",
        )
        ICP.set_param(
            "spa.booking_calendar_hex_text_color_cancel",
            self._normalize_hex_color(self.booking_calendar_hex_text_color_cancel) or "",
        )
        ICP.set_param(
            "spa.booking_calendar_hex_color_draft_weekly",
            self._normalize_hex_color(self.booking_calendar_hex_color_draft_weekly) or "",
        )
        ICP.set_param(
            "spa.booking_calendar_hex_color_draft_past_created",
            self._normalize_hex_color(self.booking_calendar_hex_color_draft_past_created) or "",
        )
        ICP.set_param(
            "spa.booking_calendar_hex_color_draft_non_session",
            self._normalize_hex_color(self.booking_calendar_hex_color_draft_non_session) or "",
        )
        ICP.set_param(
            "spa.booking_calendar_hex_color_draft_hair_removal",
            self._normalize_hex_color(self.booking_calendar_hex_color_draft_hair_removal) or "",
        )
        ICP.set_param(
            "spa.booking_calendar_hex_color_draft_expert_only",
            self._normalize_hex_color(self.booking_calendar_hex_color_draft_expert_only) or "",
        )
        ICP.set_param(
            "spa.booking_calendar_hex_text_color_draft_weekly",
            self._normalize_hex_color(self.booking_calendar_hex_text_color_draft_weekly) or "",
        )
        ICP.set_param(
            "spa.booking_calendar_hex_text_color_draft_past_created",
            self._normalize_hex_color(self.booking_calendar_hex_text_color_draft_past_created) or "",
        )
        ICP.set_param(
            "spa.booking_calendar_hex_text_color_draft_non_session",
            self._normalize_hex_color(self.booking_calendar_hex_text_color_draft_non_session) or "",
        )
        ICP.set_param(
            "spa.booking_calendar_hex_text_color_draft_hair_removal",
            self._normalize_hex_color(self.booking_calendar_hex_text_color_draft_hair_removal) or "",
        )
        ICP.set_param(
            "spa.booking_calendar_hex_text_color_draft_expert_only",
            self._normalize_hex_color(self.booking_calendar_hex_text_color_draft_expert_only) or "",
        )
        ICP.set_param(
            "spa.booking_calendar_hair_removal_category_id",
            str(self.booking_calendar_hair_removal_category_id.id or 0),
        )

    @api.constrains(
        "booking_calendar_hex_color_draft",
        "booking_calendar_hex_color_confirmed",
        "booking_calendar_hex_color_doing",
        "booking_calendar_hex_color_done",
        "booking_calendar_hex_color_cancel",
        "booking_calendar_hex_text_color_draft",
        "booking_calendar_hex_text_color_confirmed",
        "booking_calendar_hex_text_color_doing",
        "booking_calendar_hex_text_color_done",
        "booking_calendar_hex_text_color_cancel",
        "booking_calendar_hex_color_draft_weekly",
        "booking_calendar_hex_color_draft_past_created",
        "booking_calendar_hex_color_draft_non_session",
        "booking_calendar_hex_color_draft_hair_removal",
        "booking_calendar_hex_color_draft_expert_only",
        "booking_calendar_hex_text_color_draft_weekly",
        "booking_calendar_hex_text_color_draft_past_created",
        "booking_calendar_hex_text_color_draft_non_session",
        "booking_calendar_hex_text_color_draft_hair_removal",
        "booking_calendar_hex_text_color_draft_expert_only",
    )
    def _check_booking_calendar_hex_colors(self):
        for rec in self:
            for fname in [
                "booking_calendar_hex_color_draft",
                "booking_calendar_hex_color_confirmed",
                "booking_calendar_hex_color_doing",
                "booking_calendar_hex_color_done",
                "booking_calendar_hex_color_cancel",
                "booking_calendar_hex_text_color_draft",
                "booking_calendar_hex_text_color_confirmed",
                "booking_calendar_hex_text_color_doing",
                "booking_calendar_hex_text_color_done",
                "booking_calendar_hex_text_color_cancel",
                "booking_calendar_hex_color_draft_weekly",
                "booking_calendar_hex_color_draft_past_created",
                "booking_calendar_hex_color_draft_non_session",
                "booking_calendar_hex_color_draft_hair_removal",
                "booking_calendar_hex_color_draft_expert_only",
                "booking_calendar_hex_text_color_draft_weekly",
                "booking_calendar_hex_text_color_draft_past_created",
                "booking_calendar_hex_text_color_draft_non_session",
                "booking_calendar_hex_text_color_draft_hair_removal",
                "booking_calendar_hex_text_color_draft_expert_only",
            ]:
                val = (getattr(rec, fname, "") or "").strip()
                if not val:
                    continue
                if not HEX_COLOR_RE.match(val):
                    raise ValidationError(
                        _("Màu HEX không hợp lệ tại trường '%s'. Ví dụ hợp lệ: #fff, #3A86FF, fff.")
                        % rec._fields[fname].string
                    )
