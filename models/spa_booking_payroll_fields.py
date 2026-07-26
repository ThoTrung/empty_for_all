# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

DEFAULT_CUSTOMER_REQUESTED_BG = "#FF8C00"
DEFAULT_CUSTOMER_REQUESTED_FG = "#000000"
CUSTOMER_REQUESTED_COLOR_STATES = ("draft", "confirmed")


class SpaServiceBookingLine(models.Model):
    _inherit = "spa.service.booking.line"

    spa_payroll_shift_kind = fields.Selection(
        [
            ("short", "Ca ngắn"),
            ("long", "Ca dài"),
        ],
        string="Loại ca (lương)",
        default="short",
        help="Nhân viên xác nhận: ca dài hay ca ngắn cho dịch vụ này.",
    )
    spa_payroll_customer_requested = fields.Boolean(
        string="Khách chủ động đặt NV này",
        default=False,
        help="Tick khi khách chủ động yêu cầu đúng nhân viên này (thường dùng cho thưởng theo ca dài).",
    )

    @api.constrains("spa_payroll_customer_requested", "staff_id")
    def _check_spa_payroll_customer_requested_requires_staff(self):
        for line in self:
            if line.spa_payroll_customer_requested and not line.staff_id:
                raise ValidationError(
                    _("Khi khách chủ động đặt NV thì phải chọn nhân viên.")
                )

    def write(self, vals):
        res = super().write(vals)
        if {"spa_payroll_shift_kind", "spa_payroll_customer_requested"} & set(vals):
            self.mapped("booking_id")._spa_payroll_sync_flags_to_sessions()
        return res


class SpaServiceBooking(models.Model):
    _inherit = "spa.service.booking"

    # Booking đơn (không dịch vụ gộp / không line): dùng các trường này.
    spa_payroll_shift_kind = fields.Selection(
        [
            ("short", "Ca ngắn"),
            ("long", "Ca dài"),
        ],
        string="Loại ca (lương)",
        default="short",
    )
    spa_payroll_customer_requested = fields.Boolean(
        string="Khách chủ động đặt NV này",
        default=False,
    )

    def _spa_payroll_is_customer_requested(self):
        """True nếu booking hoặc bất kỳ line nào được tick «Khách chủ động đặt NV»."""
        self.ensure_one()
        if self.spa_payroll_customer_requested:
            return True
        return any(self.booking_line_ids.mapped("spa_payroll_customer_requested"))

    def _spa_payroll_get_customer_requested_colors(self):
        """Trả về (bg_hex, fg_hex) từ ICP; bg luôn có default cam."""
        ICP = self.env["ir.config_parameter"].sudo()

        def norm(val, default=""):
            v = (val or "").strip() or default
            if not v:
                return ""
            return v if v.startswith("#") else f"#{v}"

        bg = norm(
            ICP.get_param(
                "spa.booking_calendar_hex_color_customer_requested",
                DEFAULT_CUSTOMER_REQUESTED_BG,
            ),
            DEFAULT_CUSTOMER_REQUESTED_BG,
        )
        fg = norm(
            ICP.get_param(
                "spa.booking_calendar_hex_text_color_customer_requested",
                DEFAULT_CUSTOMER_REQUESTED_FG,
            ),
            "",
        )
        if not fg:
            fg = self._spa_pick_text_color_bw(bg) or DEFAULT_CUSTOMER_REQUESTED_FG
        return bg, fg

    def _spa_payroll_applies_customer_requested_color(self):
        self.ensure_one()
        return (
            self.state in CUSTOMER_REQUESTED_COLOR_STATES
            and self._spa_payroll_is_customer_requested()
        )

    @api.constrains("spa_payroll_customer_requested", "staff_ids", "is_composite_booking")
    def _check_spa_payroll_customer_requested_requires_staff(self):
        for rec in self:
            # Booking gộp: flag nằm trên line; staff bắt buộc qua constraint line.
            if rec.is_composite_booking:
                continue
            if rec.spa_payroll_customer_requested and not rec.staff_ids:
                raise ValidationError(
                    _("Khi khách chủ động đặt NV thì phải chọn nhân viên.")
                )

    @api.depends(
        "state",
        "spa_payroll_customer_requested",
        "booking_line_ids.spa_payroll_customer_requested",
    )
    def _compute_state_calendar_hex_color(self):
        override = self.filtered(lambda r: r._spa_payroll_applies_customer_requested_color())
        for rec in override:
            bg, _fg = rec._spa_payroll_get_customer_requested_colors()
            rec.state_calendar_hex_color = bg
        remaining = self - override
        if remaining:
            super(SpaServiceBooking, remaining)._compute_state_calendar_hex_color()

    @api.depends(
        "state",
        "spa_payroll_customer_requested",
        "booking_line_ids.spa_payroll_customer_requested",
    )
    def _compute_state_calendar_hex_text_color(self):
        override = self.filtered(lambda r: r._spa_payroll_applies_customer_requested_color())
        for rec in override:
            _bg, fg = rec._spa_payroll_get_customer_requested_colors()
            rec.state_calendar_hex_text_color = fg
        remaining = self - override
        if remaining:
            super(SpaServiceBooking, remaining)._compute_state_calendar_hex_text_color()

    @api.depends(
        "state",
        "booking_kind",
        "non_session_offering_id",
        "recurring_parent_id",
        "recurring_is_active",
        "create_date",
        "product_id",
        "card_id",
        "card_id.product_id",
        "non_session_offering_id.product_id",
        "spa_payroll_customer_requested",
        "booking_line_ids.spa_payroll_customer_requested",
    )
    def _compute_draft_special_colors(self):
        """Customer-requested thắng mọi màu draft đặc biệt khi state=draft."""
        override = self.filtered(
            lambda r: r.state == "draft" and r._spa_payroll_is_customer_requested()
        )
        for rec in override:
            bg, fg = rec._spa_payroll_get_customer_requested_colors()
            rec.draft_special_hex_color = bg
            rec.draft_special_hex_text_color = fg
        remaining = self - override
        if remaining:
            super(SpaServiceBooking, remaining)._compute_draft_special_colors()

    def write(self, vals):
        res = super().write(vals)
        flag_keys = {"spa_payroll_shift_kind", "spa_payroll_customer_requested"}
        line_touched = any(
            k.startswith("booking_line_ids") for k in vals
        ) or "booking_line_ids" in vals
        if flag_keys.intersection(vals) or line_touched:
            self._spa_payroll_sync_flags_to_sessions()
        return res

    def _spa_payroll_sync_flags_to_sessions(self):
        """Đẩy flag lương từ booking sang session liên kết (chưa khóa trên phiếu done)."""
        Session = self.env["spa.treatment.session"]
        for booking in self:
            sessions = Session.search([("booking_id", "=", booking.id)])
            if not sessions:
                continue
            flag_vals = Session._spa_payroll_flags_vals_from_booking(booking)
            # Không ghi đè session nếu đã nằm trên phiếu lương done (chi tiết buổi làm).
            locked_ids = set()
            if sessions:
                SvcLine = self.env["spa.staff.payroll.service.line"].sudo()
                locked = SvcLine.search([
                    ("session_id", "in", sessions.ids),
                    ("payroll_id.state", "=", "done"),
                ])
                locked_ids = set(locked.mapped("session_id").ids)
            to_sync = sessions.filtered(lambda s: s.id not in locked_ids)
            if to_sync:
                to_sync.with_context(spa_payroll_skip_booking_flag_sync=True).write(flag_vals)
