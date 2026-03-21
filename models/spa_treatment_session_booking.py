# -*- coding: utf-8 -*-

from odoo import api, fields, models


class SpaTreatmentSession(models.Model):
    _inherit = "spa.treatment.session"

    booking_id = fields.Many2one(
        "spa.service.booking",
        string="Đặt lịch",
        readonly=True,
        help="Đặt lịch tạo ra buổi trị liệu này (khi bấm Hoàn thành).",
    )

    @api.depends(
        "card_id",
        "card_id.partner_id",
        "card_id.product_id",
        "booking_id",
        "booking_id.partner_id",
        "booking_id.product_id",
        "booking_id.booking_kind",
        "booking_id.non_session_offering_id",
        "booking_id.non_session_offering_id.product_id",
    )
    def _compute_session_partner_product(self):
        for rec in self:
            if rec.card_id:
                rec.partner_id = rec.card_id.partner_id
                rec.product_id = rec.card_id.product_id
            elif rec.booking_id:
                b = rec.booking_id
                rec.partner_id = b.partner_id
                if (
                    b.booking_kind == "non_session"
                    and b.non_session_offering_id
                    and b.non_session_offering_id.product_id
                ):
                    rec.product_id = b.non_session_offering_id.product_id
                else:
                    rec.product_id = b.product_id
            else:
                rec.partner_id = False
                rec.product_id = False
