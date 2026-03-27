# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class BookingShiftConfig(models.Model):
    _name = "booking.shift.config"
    _description = "Cau hinh ca lam cho dat lich"

    name = fields.Char(default="Cau hinh ca lam", required=True)
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
        """Mot ngay chi can 1 cau hinh ca lam."""
        if not shift_date:
            shift_date = fields.Date.context_today(self)
        if isinstance(shift_date, str):
            shift_date = fields.Date.from_string(shift_date)

        config = self.search([("shift_date", "=", shift_date)], limit=1)
        if not config:
            config = self.create({"name": _("Cau hinh ca lam"), "shift_date": shift_date})
        return config

    @api.model
    def action_open_config_modal(self, shift_date=None):
        config = self.get_or_create_for_date(shift_date)
        return {
            "type": "ir.actions.act_window",
            "name": _("Ca lam"),
            "res_model": "booking.shift.config",
            "res_id": config.id,
            "view_mode": "form",
            "views": [(False, "form")],
            "target": "new",
            "context": dict(self.env.context),
        }

    def action_apply_shift_config(self):
        self.ensure_one()
        # Backward compatibility:
        # keep syncing to res.users so existing flows depending on
        # spa_shift_start_hour / spa_shift_duration_hours still work.
        for line in self.line_ids:
            if not line.user_ids:
                continue
            start_hour_float = float(line.shift_start_time_hours or 0)
            line.user_ids.write({
                "spa_shift_start_hour": start_hour_float,
                "spa_shift_duration_hours": line.shift_duration_hours,
            })
        return {"type": "ir.actions.act_window_close"}


class BookingShiftConfigLine(models.Model):
    _name = "booking.shift.config.line"
    _description = "Dong cau hinh ca lam"

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
