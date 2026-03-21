# -*- coding: utf-8 -*-

from odoo import api, fields, models


class SpaTreatmentCard(models.Model):
    _inherit = "spa.treatment.card"

    booking_ids = fields.One2many(
        "spa.service.booking",
        "card_id",
        string="Đặt lịch",
        help="Các đặt lịch dùng thẻ này (để computed reserved_by_bookings phụ thuộc đúng).",
    )
    reserved_by_bookings = fields.Integer(
        string="Đang đặt (chưa hoàn thành)",
        compute="_compute_reserved_by_bookings",
        store=True,
        help="Số đặt lịch trạng thái Đã xác nhận / Đang phục vụ dùng thẻ này (chưa bấm Hoàn thành).",
    )
    available_for_booking = fields.Integer(
        string="Còn cho đặt lịch",
        compute="_compute_available_for_booking",
        store=True,
        help="remaining_sessions trừ đi số đặt lịch đang giữ thẻ (Đã xác nhận, Đang phục vụ). Chỉ hiển thị thẻ khi > 0.",
    )

    @api.depends("booking_ids.state")
    def _compute_reserved_by_bookings(self):
        for card in self:
            card.reserved_by_bookings = len(
                card.booking_ids.filtered(lambda b: b.state in ("draft", "confirmed", "doing"))
            )

    @api.depends("remaining_sessions", "reserved_by_bookings")
    def _compute_available_for_booking(self):
        for card in self:
            card.available_for_booking = max(0, card.remaining_sessions - card.reserved_by_bookings)
