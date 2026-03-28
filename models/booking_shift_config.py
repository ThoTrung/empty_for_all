# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class BookingShiftConfig(models.Model):
    _name = "booking.shift.config"
    _description = "Cấu hình ca làm cho dat lich"

    name = fields.Char(default="Cấu hình ca làm", required=True)
    shift_date = fields.Date(
        string="Ngay",
        index=True,
        default=lambda self: fields.Date.context_today(self),
    )
    line_ids = fields.One2many(
        "booking.shift.config.line",
        "config_id",
        string="Dòng cấu hình",
    )

    @api.model
    def get_or_create_for_date(self, shift_date):
        """Mot ngay chi can 1 cau hinh ca làm."""
        if not shift_date:
            shift_date = fields.Date.context_today(self)
        if isinstance(shift_date, str):
            shift_date = fields.Date.from_string(shift_date)

        config = self.search([("shift_date", "=", shift_date)], limit=1)
        if not config:
            config = self.create({"name": _("Cấu hình ca làm"), "shift_date": shift_date})
        return config

    @api.model
    def get_user_shift_map_for_date(self, shift_date):
        """
        Trả về dict user_id -> (shift_start_time_hours, shift_duration_hours) theo cấu hình ca
        trong booking.shift.config cho đúng shift_date. duration_hours == 0 nghỉ ca ngày đó.
        Nếu không có bản ghi config cho ngày, trả về {}.
        """
        if not shift_date:
            return {}
        if isinstance(shift_date, str):
            shift_date = fields.Date.from_string(shift_date)
        cfg = self.search([("shift_date", "=", shift_date)], limit=1)
        if not cfg:
            return {}
        mapping = {}
        for line in cfg.line_ids:
            dur = float(line.shift_duration_hours or 0)
            st = float(line.shift_start_time_hours or 0)
            for uid in line.user_ids.ids:
                mapping[uid] = (st, dur)
        return mapping

    def _fill_lines_from_nearest_previous_day_if_empty(self):
        """
        Khi form ca làm không có dòng nào: sao chép toàn bộ dòng (giờ, thời lượng, NV)
        từ cấu hình ngày trước **gần nhất** (shift_date nhỏ hơn) mà vẫn có ít nhất một dòng.
        Bỏ qua các ngày chỉ có bản ghi rỗng.
        """
        self.ensure_one()
        if self.line_ids:
            return
        if not self.shift_date:
            return
        # Odoo 17 không cho order theo đường dẫn related (config_id.shift_date) trên model line.
        candidates = self.search(
            [("shift_date", "<", self.shift_date)],
            order="shift_date desc",
        )
        source = None
        for cand in candidates:
            if cand.line_ids:
                source = cand
                break
        if not source:
            return
        Line = self.env["booking.shift.config.line"]
        for line in source.line_ids:
            Line.create(
                {
                    "config_id": self.id,
                    "name": line.name,
                    "shift_start_time_hours": line.shift_start_time_hours,
                    "shift_duration_hours": line.shift_duration_hours,
                    "user_ids": [(6, 0, line.user_ids.ids)],
                }
            )

    @api.model
    def action_open_config_modal(self, shift_date=None):
        config = self.get_or_create_for_date(shift_date)
        config._fill_lines_from_nearest_previous_day_if_empty()
        return {
            "type": "ir.actions.act_window",
            "name": _("Ca làm"),
            "res_model": "booking.shift.config",
            "res_id": config.id,
            "view_mode": "form",
            "views": [(False, "form")],
            "target": "new",
            "context": dict(self.env.context),
        }

    def action_apply_shift_config(self):
        """Đóng modal. Ca làm theo ngày chỉ lưu trên booking.shift.config (không ghi res.users)."""
        self.ensure_one()
        return {"type": "ir.actions.act_window_close"}


class BookingShiftConfigLine(models.Model):
    _name = "booking.shift.config.line"
    _description = "Dòng cấu hình ca làm"

    config_id = fields.Many2one(
        "booking.shift.config",
        required=True,
        ondelete="cascade",
    )
    name = fields.Char(
        string="Tên",
        required=True,
        default="",
    )
    shift_start_time_hours = fields.Float(
        string="Giờ bắt đầu ca (Giờ:Phút)",
        required=True,
        default=8.0,
    )
    shift_duration_hours = fields.Float(
        string="Thời lượng ca",
        required=True,
        default=10.0,
    )
    user_ids = fields.Many2many(
        "res.users",
        "booking_shift_config_line_user_rel",
        "line_id",
        "user_id",
        string="Nhân viên",
        domain=[("share", "=", False)],
    )

    @api.constrains("shift_start_time_hours", "shift_duration_hours")
    def _check_shift_values(self):
        for rec in self:
            if rec.shift_start_time_hours < 0 or rec.shift_start_time_hours >= 24:
                raise ValidationError(_("Giờ bắt đầu ca phải nằm trong khoảng 0-23."))
            if rec.shift_duration_hours < 0:
                raise ValidationError(_("Thời lượng ca phải >= 0."))
