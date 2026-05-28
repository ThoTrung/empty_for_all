# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo import api, fields, models, _
from markupsafe import Markup, escape
from odoo.exceptions import ValidationError

from .booking_schedule_sanitize import (
    CTX_SCHEDULE_END_ONLY_WRITE,
    duration_minutes_between,
    is_intentional_line_end_resize,
    is_stale_longer_force_saved_end,
    sanitize_line_write_vals,
)


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
    product_internal_ref = fields.Char(
        string="Mã dịch vụ",
        related="product_id.default_code",
        store=False,
        readonly=True,
    )
    staff_id = fields.Many2one("res.users", string="Nhân viên", domain=[("share", "=", False)])
    suggested_staff_html = fields.Html(
        string="Nhân viên gợi ý (luân ca)",
        compute="_compute_suggested_staff_html",
        store=False,
        sanitize=False,
        help="Chỉ dùng hiển thị trong modal chọn NV cho từng bước dịch vụ con.",
    )
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
            if not rec.start_datetime or not rec.end_datetime:
                continue
            new_end = fields.Datetime.to_datetime(rec.end_datetime)
            if rec.duration_minutes and not rec.env.context.get(CTX_SCHEDULE_END_ONLY_WRITE):
                if is_stale_longer_force_saved_end(
                    rec.start_datetime, rec.duration_minutes, new_end
                ):
                    continue
                min_end = fields.Datetime.to_datetime(rec.start_datetime) + timedelta(
                    minutes=max(int(rec.duration_minutes or 0), 1)
                )
                if new_end < min_end - timedelta(seconds=1):
                    continue
            if new_end > rec.start_datetime:
                delta = new_end - fields.Datetime.to_datetime(rec.start_datetime)
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

    @api.depends("product_id", "start_datetime", "end_datetime", "duration_minutes", "booking_id")
    def _compute_suggested_staff_html(self):
        for rec in self:
            if not rec.product_id or not rec.start_datetime:
                rec.suggested_staff_html = ""
                continue
            end_dt = rec.end_datetime
            if not end_dt:
                dm = int(rec.duration_minutes or 0)
                dm = max(1, dm) if dm else 60
                end_dt = rec.start_datetime + timedelta(minutes=dm)
            Booking = rec.env["spa.service.booking"]
            ordered_ids = Booking._spa_rotation_ordered_staff_ids_by_history(
                product_id=rec.product_id.id,
                start_dt=rec.start_datetime,
                end_dt=end_dt,
                booking_id=rec.booking_id.id if rec.booking_id else None,
            )
            ordered_ids = list(ordered_ids or [])

            # Dịch vụ gộp: tránh gợi ý NV đã được chọn ở các bước khác (trong cùng booking) ở vị trí đầu.
            # Mục tiêu: luân ca giữa các bước, không đề xuất lặp người đứng đầu khi đã chọn ở bước trước.
            if rec.booking_id and rec.booking_id.booking_line_ids:
                assigned_ids = set(
                    rec.booking_id.booking_line_ids.filtered(
                        lambda l: l.id != rec.id and l.staff_id
                    ).mapped("staff_id").ids
                )
                if assigned_ids:
                    ordered_ids = [uid for uid in ordered_ids if uid not in assigned_ids] + [
                        uid for uid in ordered_ids if uid in assigned_ids
                    ]

            ordered_ids = ordered_ids[:5]
            if not ordered_ids:
                rec.suggested_staff_html = Markup("<i>Không có nhân viên phù hợp</i>")
                continue
            staffs = rec.env["res.users"].browse(ordered_ids)
            first_id = ordered_ids[0] if ordered_ids else False
            items = []
            for uid in ordered_ids:
                staff = staffs.filtered(lambda s: s.id == uid)[:1]
                if not staff:
                    continue
                css = "active" if uid == first_id else ""
                items.append(
                    f'<li class="list-group-item {css}">{escape(staff[0].name or staff[0].login)}</li>'
                )
            rec.suggested_staff_html = Markup(
                '<div class="o_spa_suggested_staff">'
                '<ul class="list-group list-group-flush mt-1">'
                + "".join(items)
                + "</ul></div>"
            )

    def action_open_assign_staff_modal(self):
        """Mở modal để chọn NV cho bước dịch vụ con (kèm gợi ý)."""
        self.ensure_one()
        self.env.user.spa_staff_raise_if_readonly_observer()
        view = self.env.ref("booking_calendar.view_spa_service_booking_line_form", raise_if_not_found=False)
        return {
            "type": "ir.actions.act_window",
            "name": _("Chọn nhân viên cho bước dịch vụ"),
            "res_model": "spa.service.booking.line",
            "res_id": self.id,
            "view_mode": "form",
            "views": [(view.id, "form")] if view else [(False, "form")],
            "target": "new",
            "context": dict(self.env.context),
        }

    @api.onchange("staff_id")
    def _onchange_staff_id_sync_booking_staff_ids(self):
        """UI helper: chọn NV cho bước -> sync booking.staff_ids (many2many) theo toàn bộ lines."""
        for rec in self:
            if rec.booking_id:
                rec.booking_id._sync_staff_ids_from_lines()

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [sanitize_line_write_vals(vals, is_create=True) for vals in vals_list]
        records = super().create(vals_list)
        for rec in records:
            if rec.booking_id:
                rec.booking_id._sync_duration_from_lines()
                rec.booking_id._sync_staff_ids_from_lines()
        return records

    def write(self, vals):
        vals = sanitize_line_write_vals(vals)
        records = self
        if set(vals.keys()) == {"end_datetime"}:
            new_end = fields.Datetime.to_datetime(vals["end_datetime"])
            if any(
                is_intentional_line_end_resize(
                    rec.start_datetime, rec.duration_minutes, new_end
                )
                for rec in self
            ):
                records = self.with_context(**{CTX_SCHEDULE_END_ONLY_WRITE: True})
                for rec in self:
                    mins = duration_minutes_between(rec.start_datetime, new_end)
                    if mins:
                        vals = dict(vals, duration_minutes=mins)
                        break
            else:
                vals.pop("end_datetime", None)
        res = super(SpaServiceBookingLine, records).write(vals)
        if "staff_id" in vals or "duration_minutes" in vals:
            for rec in self:
                if rec.booking_id:
                    rec.booking_id._sync_duration_from_lines()
                    rec.booking_id._sync_staff_ids_from_lines()
        return res

    def unlink(self):
        bookings = self.mapped("booking_id")
        res = super().unlink()
        for b in bookings:
            b._sync_duration_from_lines()
            b._sync_staff_ids_from_lines()
        return res
