# -*- coding: utf-8 -*-

from datetime import datetime, timedelta

from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "booking_calendar", "spa_security")
class TestBookingStaffReadonlyObserver(TransactionCase):
    """Đặt lịch: user chỉ read-only không được write booking."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.partner = cls.env["res.partner"].create(
            {"name": "Booking RO Partner", "is_company": False}
        )
        cls.staff = cls.env.ref("base.user_admin")
        tmpl = cls.env["product.template"].create(
            {
                "name": "RO Booking Svc",
                "detailed_type": "service",
                "list_price": 50,
                "spa_sessions_per_unit": 5,
                "spa_duration_minutes": 60,
            }
        )
        cls.product = tmpl.product_variant_id
        cls.bed = cls.env["spa.bed"].create({"name": "Bed RO BK"})
        cls.card = cls.env["spa.treatment.card"].create(
            {
                "name": "Card RO BK",
                "partner_id": cls.partner.id,
                "product_id": cls.product.id,
                "total_sessions": 10,
                "duration_minutes": 60,
            }
        )

    def _readonly_user(self, slug):
        return (
            self.env["res.users"]
            .sudo()
            .create(
                {
                    "name": "RO booking %s" % slug,
                    "login": "ro_bk_%s" % slug,
                    "password": "ro_bk_pw",
                    "groups_id": [
                        (
                            6,
                            0,
                            [
                                self.env.ref("base.group_user").id,
                                self.env.ref("spa.group_spa_staff_readonly").id,
                            ],
                        )
                    ],
                }
            )
        )

    def test_readonly_user_cannot_write_booking(self):
        start = datetime.now() + timedelta(days=5)
        start = start.replace(hour=12, minute=0, second=0, microsecond=0)
        booking = self.env["spa.service.booking"].create(
            {
                "partner_id": self.partner.id,
                "card_id": self.card.id,
                "product_id": self.product.id,
                "start_datetime": start,
                "duration": 60,
                "bed_id": False,
            }
        )
        ro = self._readonly_user("write_%s" % booking.id)
        with self.assertRaises(AccessError):
            booking.with_user(ro).write({"note": "nope"})

    def test_set_calendar_config_blocked_for_readonly(self):
        ro = self._readonly_user("cal_cfg")
        with self.assertRaises(AccessError):
            self.env["spa.service.booking"].with_user(ro).set_calendar_display_config(
                pixels_per_hour=72
            )

    def test_readonly_user_sees_only_assigned_bookings(self):
        start = datetime.now() + timedelta(days=6)
        start = start.replace(hour=10, minute=0, second=0, microsecond=0)
        ro = self._readonly_user("visibility")

        booking_visible = self.env["spa.service.booking"].create(
            {
                "partner_id": self.partner.id,
                "card_id": self.card.id,
                "product_id": self.product.id,
                "start_datetime": start,
                "duration": 60,
                "staff_ids": [(6, 0, [ro.id])],
            }
        )
        booking_hidden = self.env["spa.service.booking"].create(
            {
                "partner_id": self.partner.id,
                "card_id": self.card.id,
                "product_id": self.product.id,
                "start_datetime": start + timedelta(hours=2),
                "duration": 60,
                "staff_ids": [(6, 0, [self.staff.id])],
            }
        )

        visible_ids = self.env["spa.service.booking"].with_user(ro).search([]).ids
        self.assertIn(booking_visible.id, visible_ids)
        self.assertNotIn(booking_hidden.id, visible_ids)

    def test_readonly_user_sees_booking_when_assigned_on_any_line(self):
        start = datetime.now() + timedelta(days=7)
        start = start.replace(hour=9, minute=0, second=0, microsecond=0)
        ro = self._readonly_user("line_visibility")

        booking = self.env["spa.service.booking"].create(
            {
                "partner_id": self.partner.id,
                "booking_kind": "card",
                "card_id": self.card.id,
                "product_id": self.product.id,
                "start_datetime": start,
                "duration": 120,
                "booking_line_ids": [
                    (0, 0, {
                        "product_id": self.product.id,
                        "staff_id": self.staff.id,
                        "start_datetime": start,
                        "duration_minutes": 60,
                    }),
                    (0, 0, {
                        "product_id": self.product.id,
                        "staff_id": ro.id,
                        "start_datetime": start + timedelta(hours=1),
                        "duration_minutes": 60,
                    }),
                ],
            }
        )

        visible_ids = self.env["spa.service.booking"].with_user(ro).search([]).ids
        self.assertIn(booking.id, visible_ids)
