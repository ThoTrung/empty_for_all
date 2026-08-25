# -*- coding: utf-8 -*-

from datetime import datetime, timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "booking_calendar", "spa_security")
class TestBookingOperator(TransactionCase):
    """Spa Booking Operator: xem confirmed/doing/done, sửa NV thực hiện, Phục vụ/Hoàn thành, không CRUD."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.partner = cls.env["res.partner"].create(
            {"name": "Booking Op Partner", "is_company": False}
        )
        cls.staff_user = cls.env.ref("base.user_admin")
        cls.staff_b = (
            cls.env["res.users"]
            .sudo()
            .create(
                {
                    "name": "Booking staff B",
                    "login": "bk_staff_b_op",
                    "password": "bk_staff_b_pw",
                    "groups_id": [(6, 0, [cls.env.ref("base.group_user").id])],
                }
            )
        )
        tmpl = cls.env["product.template"].create(
            {
                "name": "Op Booking Svc",
                "detailed_type": "service",
                "list_price": 50,
                "spa_sessions_per_unit": 5,
                "spa_duration_minutes": 60,
            }
        )
        cls.product = tmpl.product_variant_id
        cls.card = cls.env["spa.treatment.card"].create(
            {
                "name": "Card Op BK",
                "partner_id": cls.partner.id,
                "product_id": cls.product.id,
                "total_sessions": 10,
                "duration_minutes": 60,
            }
        )

    def _operator_user(self, slug):
        return (
            self.env["res.users"]
            .sudo()
            .create(
                {
                    "name": "Booking op %s" % slug,
                    "login": "bk_op_%s" % slug,
                    "password": "bk_op_pw",
                    "groups_id": [
                        (
                            6,
                            0,
                            [
                                self.env.ref("base.group_user").id,
                                self.env.ref("spa.group_spa_booking_operator").id,
                            ],
                        )
                    ],
                }
            )
        )

    def _ensure_shift(self, start_dt, user_ids):
        d = fields.Datetime.context_timestamp(self.env.user, start_dt).date()
        cfg = self.env["booking.shift.config"].search([("shift_date", "=", d)], limit=1)
        if not cfg:
            cfg = self.env["booking.shift.config"].create(
                {"name": "Op test ca", "shift_date": d}
            )
        existing = cfg.line_ids.mapped("user_ids").ids
        missing = [uid for uid in user_ids if uid not in existing]
        if missing or not cfg.line_ids:
            self.env["booking.shift.config.line"].create(
                {
                    "config_id": cfg.id,
                    "name": "Ca op",
                    "shift_start_time_hours": 0.0,
                    "shift_duration_hours": 24.0,
                    "user_ids": [(6, 0, list(user_ids))],
                }
            )

    def _make_booking(self, state="confirmed", staff_ids=None, hours_offset=0):
        start = datetime.now() + timedelta(days=3, hours=hours_offset)
        start = start.replace(minute=0, second=0, microsecond=0)
        if staff_ids:
            self._ensure_shift(start, staff_ids)
        vals = {
            "partner_id": self.partner.id,
            "card_id": self.card.id,
            "product_id": self.product.id,
            "start_datetime": start,
            "duration": 60,
            "state": state,
            "staff_id": False,
        }
        if staff_ids is not None:
            vals["staff_ids"] = [(6, 0, staff_ids)]
        else:
            vals["staff_ids"] = [(5, 0, 0)]
        return self.env["spa.service.booking"].create(vals)

    def _make_composite(self, state="confirmed", hours_offset=0):
        start = datetime.now() + timedelta(days=4, hours=hours_offset)
        start = start.replace(minute=0, second=0, microsecond=0)
        self._ensure_shift(start, [self.staff_user.id, self.staff_b.id])
        return self.env["spa.service.booking"].create(
            {
                "partner_id": self.partner.id,
                "card_id": self.card.id,
                "product_id": self.product.id,
                "start_datetime": start,
                "duration": 120,
                "state": state,
                "staff_id": False,
                "booking_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "start_datetime": start,
                            "duration_minutes": 60,
                            "staff_id": self.staff_user.id,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "start_datetime": start + timedelta(minutes=60),
                            "duration_minutes": 60,
                            "staff_id": self.staff_user.id,
                        },
                    ),
                ],
            }
        )

    def test_operator_sees_confirmed_doing_done_not_draft_cancel(self):
        op = self._operator_user("visibility")
        draft = self._make_booking("draft", hours_offset=0)
        confirmed = self._make_booking("confirmed", hours_offset=1)
        doing = self._make_booking("doing", staff_ids=[self.staff_user.id], hours_offset=2)
        done = self._make_booking("done", staff_ids=[self.staff_user.id], hours_offset=3)
        cancel = self._make_booking("cancel", hours_offset=4)

        visible_ids = self.env["spa.service.booking"].with_user(op).search([]).ids
        self.assertIn(confirmed.id, visible_ids)
        self.assertIn(doing.id, visible_ids)
        self.assertIn(done.id, visible_ids)
        self.assertNotIn(draft.id, visible_ids)
        self.assertNotIn(cancel.id, visible_ids)

    def test_operator_cannot_create_write_unlink(self):
        op = self._operator_user("crud")
        booking = self._make_booking(
            "confirmed", staff_ids=[self.staff_user.id], hours_offset=5
        )
        Booking = self.env["spa.service.booking"].with_user(op)
        with self.assertRaises(AccessError):
            Booking.create(
                {
                    "partner_id": self.partner.id,
                    "card_id": self.card.id,
                    "product_id": self.product.id,
                    "start_datetime": datetime.now() + timedelta(days=10),
                    "duration": 60,
                }
            )
        with self.assertRaises(AccessError):
            booking.with_user(op).write({"note": "nope"})
        with self.assertRaises(AccessError):
            booking.with_user(op).unlink()

    def test_operator_can_write_staff_ids_on_confirmed_and_doing(self):
        op = self._operator_user("staff_ok")
        booking = self._make_booking(
            "confirmed",
            staff_ids=[self.staff_user.id, self.staff_b.id],
            hours_offset=10,
        )
        booking.with_user(op).write({"staff_ids": [(6, 0, [self.staff_b.id])]})
        self.assertEqual(booking.staff_ids, self.staff_b)

        booking.with_user(op).action_doing()
        self.assertEqual(booking.state, "doing")
        booking.with_user(op).write({"staff_ids": [(6, 0, [self.staff_user.id])]})
        self.assertEqual(booking.staff_ids, self.staff_user)

    def test_operator_form_save_drops_display_end_keeps_staff(self):
        op = self._operator_user("form_save")
        booking = self._make_booking(
            "confirmed",
            staff_ids=[self.staff_user.id, self.staff_b.id],
            hours_offset=11,
        )
        old_end = booking.display_end_datetime
        booking.with_user(op).write(
            {
                "staff_ids": [(6, 0, [self.staff_b.id])],
                "display_end_datetime": old_end,
            }
        )
        self.assertEqual(booking.staff_ids, self.staff_b)
        self.assertEqual(booking.display_end_datetime, old_end)

    def test_operator_cannot_write_duration_or_partner(self):
        op = self._operator_user("no_duration")
        booking = self._make_booking(
            "confirmed", staff_ids=[self.staff_user.id], hours_offset=12
        )
        old_duration = booking.duration
        with self.assertRaises(AccessError):
            booking.with_user(op).write({"duration": 90})
        with self.assertRaises(AccessError):
            booking.with_user(op).write({"partner_id": self.partner.id, "note": "x"})
        self.assertEqual(booking.duration, old_duration)

    def test_operator_cannot_write_staff_when_done(self):
        op = self._operator_user("done_staff")
        booking = self._make_booking(
            "confirmed",
            staff_ids=[self.staff_user.id],
            hours_offset=13,
        )
        booking.with_user(op).action_doing()
        booking.with_user(op).action_done()
        self.assertEqual(booking.state, "done")
        with self.assertRaises(AccessError):
            booking.with_user(op).write({"staff_ids": [(6, 0, [self.staff_b.id])]})
        self.assertEqual(booking.staff_ids, self.staff_user)

    def test_operator_can_write_composite_line_staff(self):
        op = self._operator_user("composite")
        booking = self._make_composite("confirmed", hours_offset=0)
        line = booking.booking_line_ids.sorted(lambda l: (l.sequence, l.id))[0]
        old_duration = line.duration_minutes
        line.with_user(op).write({"staff_id": self.staff_b.id})
        self.assertEqual(line.staff_id, self.staff_b)
        self.assertEqual(line.duration_minutes, old_duration)
        self.assertIn(self.staff_b, booking.staff_ids)

    def test_operator_booking_line_ids_command_staff_only(self):
        op = self._operator_user("o2m")
        booking = self._make_composite("confirmed", hours_offset=1)
        line = booking.booking_line_ids.sorted(lambda l: (l.sequence, l.id))[0]
        booking.with_user(op).write(
            {
                "booking_line_ids": [(1, line.id, {"staff_id": self.staff_b.id})],
            }
        )
        self.assertEqual(line.staff_id, self.staff_b)

    def test_operator_rejects_line_duration_and_create_unlink(self):
        op = self._operator_user("line_crud")
        booking = self._make_composite("confirmed", hours_offset=2)
        line = booking.booking_line_ids[:1]
        old_duration = line.duration_minutes
        with self.assertRaises(AccessError):
            line.with_user(op).write({"duration_minutes": 90})
        with self.assertRaises(AccessError):
            booking.with_user(op).write(
                {
                    "booking_line_ids": [
                        (1, line.id, {"staff_id": self.staff_b.id, "duration_minutes": 90})
                    ]
                }
            )
        with self.assertRaises(AccessError):
            self.env["spa.service.booking.line"].with_user(op).create(
                {
                    "booking_id": booking.id,
                    "product_id": self.product.id,
                    "start_datetime": booking.start_datetime,
                    "duration_minutes": 30,
                }
            )
        with self.assertRaises(AccessError):
            line.with_user(op).unlink()
        self.assertEqual(line.duration_minutes, old_duration)

    def test_operator_can_open_assign_staff_modal(self):
        op = self._operator_user("modal")
        booking = self._make_composite("confirmed", hours_offset=3)
        line = booking.booking_line_ids[:1]
        action = line.with_user(op).action_open_assign_staff_modal()
        self.assertEqual(action.get("res_model"), "spa.service.booking.line")
        self.assertEqual(action.get("res_id"), line.id)

    def test_operator_form_and_calendar_arch(self):
        form = self.env.ref("booking_calendar.view_spa_service_booking_form_operator")
        form_arch = self.env["spa.service.booking"].get_view(
            view_id=form.id, view_type="form"
        )["arch"]
        self.assertIn('edit="1"', form_arch)
        self.assertIn('name="staff_ids"', form_arch)
        cal = self.env.ref("booking_calendar.view_spa_service_booking_calendar_operator")
        cal_arch = self.env["spa.service.booking"].get_view(
            view_id=cal.id, view_type="calendar"
        )["arch"]
        self.assertIn("display_start_datetime", cal_arch)

    def test_action_doing_requires_staff(self):
        op = self._operator_user("no_staff")
        booking = self._make_booking("confirmed", staff_ids=[], hours_offset=6)
        with self.assertRaises(UserError):
            booking.with_user(op).action_doing()

    def test_operator_action_doing_and_done(self):
        op = self._operator_user("serve")
        booking = self._make_booking(
            "confirmed", staff_ids=[self.staff_user.id], hours_offset=7
        )
        booking.with_user(op).action_doing()
        self.assertEqual(booking.state, "doing")
        booking.with_user(op).action_done()
        self.assertEqual(booking.state, "done")
        self.assertTrue(booking.session_id)

    def test_operator_cannot_confirm_or_cancel(self):
        op = self._operator_user("confirm")
        booking = self._make_booking(
            "confirmed", staff_ids=[self.staff_user.id], hours_offset=8
        )
        with self.assertRaises(AccessError):
            booking.with_user(op).action_cancel()

    def test_staff_user_not_restricted_by_operator_rule(self):
        """User with Spa Staff still sees draft even if also operator."""
        user = (
            self.env["res.users"]
            .sudo()
            .create(
                {
                    "name": "Staff+Op",
                    "login": "bk_staff_op_mix",
                    "password": "pw",
                    "groups_id": [
                        (
                            6,
                            0,
                            [
                                self.env.ref("base.group_user").id,
                                self.env.ref("spa.group_spa_staff").id,
                                self.env.ref("spa.group_spa_booking_operator").id,
                            ],
                        )
                    ],
                }
            )
        )
        draft = self._make_booking("draft", hours_offset=9)
        visible_ids = self.env["spa.service.booking"].with_user(user).search([]).ids
        self.assertIn(draft.id, visible_ids)
        draft.with_user(user).write({"note": "staff still writes"})
        self.assertEqual(draft.note, "staff still writes")

    def test_set_calendar_config_blocked_for_operator(self):
        op = self._operator_user("cal_cfg")
        with self.assertRaises(AccessError):
            self.env["spa.service.booking"].with_user(op).set_calendar_display_config(
                pixels_per_hour=72
            )

    def test_operator_can_write_staff_outside_shift_user_ids(self):
        """Operator được ghi M2M NV ngoài ca trên booking đơn."""
        op = self._operator_user("outside_m2m")
        start = datetime.now() + timedelta(days=5)
        start = start.replace(hour=19, minute=0, second=0, microsecond=0)
        d = fields.Datetime.context_timestamp(self.env.user, start).date()
        cfg = self.env["booking.shift.config"].search([("shift_date", "=", d)], limit=1)
        if cfg:
            cfg.line_ids.unlink()
        else:
            cfg = self.env["booking.shift.config"].create(
                {"name": "Op ca ngoài giờ", "shift_date": d}
            )
        self.env["booking.shift.config.line"].create({
            "config_id": cfg.id,
            "name": "Ca ngắn",
            "shift_start_time_hours": 8.0,
            "shift_duration_hours": 2.0,
            "user_ids": [(6, 0, [self.staff_user.id, self.staff_b.id])],
        })
        booking = self.env["spa.service.booking"].create({
            "partner_id": self.partner.id,
            "card_id": self.card.id,
            "product_id": self.product.id,
            "start_datetime": start,
            "duration": 60,
            "state": "confirmed",
            "staff_ids": [(6, 0, [self.staff_user.id])],
            "staff_outside_shift": True,
            "staff_outside_shift_user_ids": [(6, 0, [self.staff_user.id])],
        })
        booking.with_user(op).write({
            "staff_ids": [(6, 0, [self.staff_user.id, self.staff_b.id])],
            "staff_outside_shift_user_ids": [(6, 0, [self.staff_user.id, self.staff_b.id])],
        })
        self.assertIn(self.staff_b, booking.staff_outside_shift_user_ids)
        self.assertIn(self.staff_user, booking.staff_outside_shift_user_ids)

    def test_operator_spa_only_app_roots(self):
        op = self._operator_user("roots")
        roots = self.env["ir.ui.menu"].with_user(op).get_user_roots()
        spa_root = self.env.ref("spa.menu_spa_root")
        self.assertEqual(
            roots,
            spa_root,
            "Booking Operator-only should leave only spa.menu_spa_root as app root",
        )
