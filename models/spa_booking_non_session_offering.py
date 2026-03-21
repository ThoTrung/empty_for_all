# -*- coding: utf-8 -*-
"""Danh mục loại lịch không trừ buổi thẻ (họp, tư vấn, đào tạo…)."""

from odoo import api, fields, models


class SpaBookingNonSessionOffering(models.Model):
    _name = "spa.booking.non_session_offering"
    _description = "Loại hoạt động không trừ buổi thẻ"
    _inherit = ["spa.booking.completion.mixin"]
    _order = "sequence, name"

    name = fields.Char(string="Tên hiển thị", required=True, translate=True)
    code = fields.Char(string="Mã", copy=False)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    product_id = fields.Many2one(
        "product.product",
        string="Dịch vụ gợi ý (tuỳ chọn)",
        domain=[("detailed_type", "=", "service")],
        help="Dùng để gợi ý mã/tên trên lịch và buổi ghi nhận (capacity theo sản phẩm nếu có).",
    )
    duration_minutes = fields.Integer(
        string="Thời lượng mặc định (phút)",
        default=60,
        help="Áp dụng khi tạo đặt lịch nếu chưa chỉnh thủ công.",
    )

    @api.model
    def create(self, vals):
        if not vals.get("code"):
            vals["code"] = self.env["ir.sequence"].next_by_code(
                "spa.booking.non_session_offering"
            ) or False
        return super().create(vals)

    def spa_complete_booking(self, booking):
        self.ensure_one()
        booking.ensure_one()
        if booking.session_id:
            booking.write({"state": "done"})
            return booking.session_id
        Session = self.env["spa.treatment.session"]
        duration_minutes = booking.duration or 0
        if duration_minutes <= 0:
            duration_minutes = self.duration_minutes or 60
        if booking.start_datetime and booking.end_datetime:
            delta = booking.end_datetime - booking.start_datetime
            d = int(round(delta.total_seconds() / 60.0))
            if d > 0:
                duration_minutes = d
        staff_ids = booking.staff_ids.ids
        therapist_id = staff_ids[0] if staff_ids else self.env.user.id
        session = Session.create({
            "card_id": False,
            "booking_id": booking.id,
            "date": booking.start_datetime,
            "therapist_id": therapist_id,
            "therapist_ids": [(6, 0, staff_ids)],
            "duration_minutes": duration_minutes,
            "note": booking.note or "",
            "state": "done",
        })
        booking.write({"state": "done", "session_id": session.id})
        return session
