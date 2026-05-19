# -*- coding: utf-8 -*-
"""Unit tests for booking_schedule_sanitize helpers (no DB)."""

from odoo.tests.common import TransactionCase

from odoo.addons.booking_calendar.models.booking_schedule_sanitize import (
    duration_minutes_between,
    is_intentional_line_end_resize,
    is_stale_longer_force_saved_end,
    sanitize_booking_write_vals,
    sanitize_line_write_vals,
)


class TestBookingScheduleSanitize(TransactionCase):
    def test_sanitize_booking_form_save_drops_display_end(self):
        vals = sanitize_booking_write_vals({
            "note": "x",
            "display_end_datetime": "2026-05-20 11:00:00",
        })
        self.assertNotIn("display_end_datetime", vals)
        self.assertNotIn("end_datetime", vals)

    def test_sanitize_booking_calendar_only_keeps_display_end(self):
        payload = {
            "display_start_datetime": "2026-05-20 10:00:00",
            "display_end_datetime": "2026-05-20 11:00:00",
        }
        vals = sanitize_booking_write_vals(payload)
        self.assertEqual(vals, payload)

    def test_sanitize_booking_start_change_drops_all_end_fields(self):
        vals = sanitize_booking_write_vals({
            "start_datetime": "2026-05-21 10:00:00",
            "display_end_datetime": "2026-05-20 11:00:00",
            "end_datetime": "2026-05-20 11:00:00",
        })
        self.assertEqual(vals, {"start_datetime": "2026-05-21 10:00:00"})

    def test_sanitize_line_form_save_drops_stale_end(self):
        vals = sanitize_line_write_vals({
            "staff_id": 1,
            "end_datetime": "2026-05-20 11:00:00",
        })
        self.assertEqual(vals, {"staff_id": 1})

    def test_sanitize_line_end_only_keeps_end(self):
        payload = {"end_datetime": "2026-05-20 10:30:00"}
        vals = sanitize_line_write_vals(payload)
        self.assertEqual(vals, payload)

    def test_stale_longer_force_saved_end_detected(self):
        self.assertTrue(is_stale_longer_force_saved_end(
            "2026-05-20 10:00:00", 45, "2026-05-20 11:00:00",
        ))

    def test_intentional_line_end_shorten(self):
        self.assertTrue(is_intentional_line_end_resize(
            "2026-05-20 10:00:00", 45, "2026-05-20 10:30:00",
        ))
        self.assertFalse(is_intentional_line_end_resize(
            "2026-05-20 10:00:00", 45, "2026-05-20 11:00:00",
        ))

    def test_duration_minutes_between(self):
        self.assertEqual(
            duration_minutes_between("2026-05-20 10:00:00", "2026-05-20 10:45:00"),
            45,
        )
