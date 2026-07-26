# -*- coding: utf-8 -*-

from odoo import api, fields, models


class SpaTreatmentSession(models.Model):
    _inherit = "spa.treatment.session"

    spa_payroll_shift_kind = fields.Selection(
        [
            ("short", "Ca ngắn"),
            ("long", "Ca dài"),
        ],
        string="Loại ca (tính lương)",
        default="short",
        copy=False,
        index=True,
        help="Đồng bộ từ đặt lịch khi có booking_id. Dùng để tính thưởng ca dài.",
    )
    spa_payroll_customer_requested = fields.Boolean(
        string="Khách chủ động đặt (tính lương)",
        default=False,
        copy=False,
        index=True,
        help="Đồng bộ từ đặt lịch khi có booking_id. Chỉ thưởng khi kèm ca dài.",
    )
    spa_payroll_flags_from_booking = fields.Boolean(
        string="Flag lương lấy từ đặt lịch",
        compute="_compute_spa_payroll_flags_from_booking",
    )

    @api.depends("booking_id")
    def _compute_spa_payroll_flags_from_booking(self):
        for rec in self:
            rec.spa_payroll_flags_from_booking = bool(rec.booking_id)

    @api.model
    def _spa_payroll_flags_vals_from_booking(self, booking):
        """Map payroll flags từ booking (header; composite: OR khách đặt trên line)."""
        if not booking:
            return {}
        kind = booking.spa_payroll_shift_kind or "short"
        if booking.is_composite_booking and booking.booking_line_ids:
            line_kinds = booking.booking_line_ids.mapped("spa_payroll_shift_kind")
            kind = "long" if "long" in line_kinds else (kind or "short")
            requested = bool(booking.spa_payroll_customer_requested) or any(
                booking.booking_line_ids.mapped("spa_payroll_customer_requested")
            )
        else:
            requested = bool(booking.spa_payroll_customer_requested)
        return {
            "spa_payroll_shift_kind": kind,
            "spa_payroll_customer_requested": requested,
        }

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            booking_id = vals.get("booking_id")
            if booking_id and (
                "spa_payroll_shift_kind" not in vals
                or "spa_payroll_customer_requested" not in vals
            ):
                booking = self.env["spa.service.booking"].browse(booking_id)
                flag_vals = self._spa_payroll_flags_vals_from_booking(booking)
                if "spa_payroll_shift_kind" not in vals and "spa_payroll_shift_kind" in flag_vals:
                    vals["spa_payroll_shift_kind"] = flag_vals["spa_payroll_shift_kind"]
                if (
                    "spa_payroll_customer_requested" not in vals
                    and "spa_payroll_customer_requested" in flag_vals
                ):
                    vals["spa_payroll_customer_requested"] = flag_vals[
                        "spa_payroll_customer_requested"
                    ]
        return super().create(vals_list)

    def write(self, vals):
        res = super().write(vals)
        if self.env.context.get("spa_payroll_skip_booking_flag_sync"):
            return res
        if "booking_id" in vals and vals.get("booking_id"):
            for rec in self:
                if not rec.booking_id:
                    continue
                flag_vals = self._spa_payroll_flags_vals_from_booking(rec.booking_id)
                to_write = {}
                if rec.spa_payroll_shift_kind != flag_vals.get("spa_payroll_shift_kind"):
                    to_write["spa_payroll_shift_kind"] = flag_vals["spa_payroll_shift_kind"]
                if rec.spa_payroll_customer_requested != flag_vals.get(
                    "spa_payroll_customer_requested"
                ):
                    to_write["spa_payroll_customer_requested"] = flag_vals[
                        "spa_payroll_customer_requested"
                    ]
                if to_write:
                    super(SpaTreatmentSession, rec).write(to_write)
        return res
