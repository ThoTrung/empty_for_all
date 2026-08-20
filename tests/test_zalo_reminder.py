# -*- coding: utf-8 -*-
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

PATH = "odoo.addons.spa_zalo_oa"


@tagged("post_install", "-at_install")
class TestZaloOa(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ICP = cls.env["ir.config_parameter"].sudo()
        cls.Message = cls.env["spa.zalo.message"]
        cls.partner = cls.env["res.partner"].create(
            {"name": "KH Test", "mobile": "0905123456"}
        )
        cls.account = cls.env["spa.zalo.oa.account"].create(
            {
                "name": "OA Test",
                "app_id": "app123",
                "secret_key": "secret123",
                "refresh_token": "rt123",
            }
        )
        cls.ICP.set_param("spa_zalo_oa.development_mode", "1")
        # DB thật (drlai) có thể đang bật whitelist demo — cô lập test.
        cls.ICP.set_param("spa_zalo_oa.whitelist_enabled", "0")
        cls.ICP.set_param("spa_zalo_oa.whitelist_phones", "")

    def _process_queue(self):
        with patch(PATH + ".zalo_oapi.in_zns_quiet_hours", return_value=False):
            self.Message._cron_process_queue()

    def _confirm_booking(self, booking):
        booking.write({"state": "confirmed"})
        return booking

    def _make_booking_in_window(self, partner, state="confirmed"):
        offering = self.env["spa.booking.non_session_offering"].create(
            {"name": "Tư vấn", "duration_minutes": 60}
        )
        booking = self.env["spa.service.booking"].create(
            {
                "partner_id": partner.id,
                "booking_kind": "non_session",
                "non_session_offering_id": offering.id,
                "start_datetime": fields.Datetime.now() + timedelta(hours=2),
                "duration": 60,
            }
        )
        if state == "confirmed":
            self._confirm_booking(booking)
        return booking

    def _enable_reminder(self):
        self.ICP.set_param("spa_zalo_oa.reminder_enabled", "1")
        self.ICP.set_param("spa_zalo_oa.reminder_template_id", "tpl_reminder")
        self.ICP.set_param("spa_zalo_oa.reminder_offset_unit", "hours")
        self.ICP.set_param("spa_zalo_oa.reminder_offset_value", "48")
        self.ICP.set_param("spa_zalo_oa.whitelist_enabled", "0")

    # ---------------- enqueue ----------------
    def test_enqueue_normalizes_phone(self):
        msg = self.Message.enqueue(
            partner=self.partner,
            event_type="booking_reminder",
            template_id="tpl1",
            template_data={"name": "KH Test"},
        )
        self.assertTrue(msg)
        self.assertEqual(msg.phone, "84905123456")
        self.assertEqual(msg.state, "queued")

    def test_enqueue_skips_optout(self):
        self.partner.zalo_optout = True
        msg = self.Message.enqueue(
            partner=self.partner,
            event_type="booking_reminder",
            template_id="tpl1",
            template_data={},
        )
        self.assertFalse(msg)

    def test_enqueue_skips_no_phone(self):
        partner = self.env["res.partner"].create({"name": "Không SĐT"})
        msg = self.Message.enqueue(
            partner=partner,
            event_type="booking_reminder",
            template_id="tpl1",
            template_data={},
        )
        self.assertFalse(msg)

    def test_enqueue_dedup_source_ref(self):
        ref = "spa.service.booking,999"
        first = self.Message.enqueue(
            partner=self.partner,
            event_type="booking_reminder",
            template_id="tpl1",
            template_data={},
            source_ref=ref,
        )
        second = self.Message.enqueue(
            partner=self.partner,
            event_type="booking_reminder",
            template_id="tpl1",
            template_data={},
            source_ref=ref,
        )
        self.assertTrue(first)
        self.assertFalse(second)

    def test_enqueue_allows_after_sent(self):
        ref = "spa.service.booking,998"
        first = self.Message.enqueue(
            partner=self.partner,
            event_type="booking_reminder",
            template_id="tpl1",
            template_data={},
            source_ref=ref,
        )
        first.write({"state": "sent"})
        second = self.Message.enqueue(
            partner=self.partner,
            event_type="booking_reminder",
            template_id="tpl1",
            template_data={},
            source_ref=ref,
        )
        self.assertTrue(second)
        self.assertNotEqual(first.id, second.id)

    # ---------------- queue processing ----------------
    def test_process_queue_success(self):
        msg = self.Message.enqueue(
            partner=self.partner,
            event_type="booking_reminder",
            template_id="tpl1",
            template_data={},
        )
        with patch(
            PATH + ".zalo_oapi.send_zns", return_value=({"msg_id": "M1"}, None)
        ), patch.object(
            type(self.account), "get_valid_access_token", return_value="tok"
        ):
            self._process_queue()
        self.assertEqual(msg.state, "sent")
        self.assertEqual(msg.zalo_msg_id, "M1")

    def test_process_queue_failure_then_failed(self):
        self.ICP.set_param("spa_zalo_oa.max_retry", "2")
        msg = self.Message.enqueue(
            partner=self.partner,
            event_type="booking_reminder",
            template_id="tpl1",
            template_data={},
        )
        with patch(
            PATH + ".zalo_oapi.send_zns", return_value=(None, "boom")
        ), patch.object(
            type(self.account), "get_valid_access_token", return_value="tok"
        ):
            self._process_queue()
            self.assertEqual(msg.state, "queued")
            self.assertEqual(msg.retry_count, 1)
            self._process_queue()
        self.assertEqual(msg.state, "failed")
        self.assertEqual(msg.retry_count, 2)

    def test_permanent_error_fails_without_retry(self):
        msg = self.Message.enqueue(
            partner=self.partner,
            event_type="booking_reminder",
            template_id="tpl1",
            template_data={},
        )
        with patch(
            PATH + ".zalo_oapi.send_zns",
            return_value=(None, "[-118] Phone has no Zalo"),
        ), patch.object(
            type(self.account), "get_valid_access_token", return_value="tok"
        ):
            self._process_queue()
        self.assertEqual(msg.state, "failed")
        self.assertEqual(msg.retry_count, 0)

    def test_quiet_hours_keeps_queued(self):
        msg = self.Message.enqueue(
            partner=self.partner,
            event_type="booking_reminder",
            template_id="tpl1",
            template_data={},
        )
        with patch(PATH + ".zalo_oapi.in_zns_quiet_hours", return_value=True):
            self.Message._cron_process_queue()
        self.assertEqual(msg.state, "queued")
        self.assertEqual(msg.retry_count, 0)

    def test_send_now_blocked_in_quiet_hours(self):
        msg = self.Message.enqueue(
            partner=self.partner,
            event_type="booking_reminder",
            template_id="tpl1",
            template_data={},
        )
        with patch(PATH + ".zalo_oapi.in_zns_quiet_hours", return_value=True):
            with self.assertRaises(UserError):
                msg.action_send_now()

    def test_send_uses_development_mode(self):
        msg = self.Message.enqueue(
            partner=self.partner,
            event_type="booking_reminder",
            template_id="tpl1",
            template_data={},
        )
        with patch(
            PATH + ".zalo_oapi.send_zns", return_value=({"msg_id": "M1"}, None)
        ) as mock_send, patch.object(
            type(self.account), "get_valid_access_token", return_value="tok"
        ):
            self._process_queue()
        self.assertTrue(mock_send.called)
        self.assertEqual(mock_send.call_args.kwargs.get("mode"), "development")
        self.assertEqual(msg.state, "sent")

    # ---------------- token refresh ----------------
    def test_token_refresh(self):
        with patch(
            PATH + ".zalo_oapi.refresh_access_token",
            return_value=(
                {"access_token": "AT", "refresh_token": "RT2", "expires_in": "90000"},
                None,
            ),
        ):
            err = self.account._do_refresh(force=True)
        self.assertFalse(err)
        self.assertEqual(self.account.access_token, "AT")
        self.assertEqual(self.account.refresh_token, "RT2")
        self.assertTrue(self.account._token_is_valid())

    def test_refresh_skipped_when_token_still_valid(self):
        with patch(
            PATH + ".zalo_oapi.refresh_access_token",
            return_value=(
                {"access_token": "AT", "refresh_token": "RT2", "expires_in": "90000"},
                None,
            ),
        ) as mock_refresh:
            self.account._do_refresh(force=True)
            mock_refresh.reset_mock()
            err = self.account._do_refresh()
        self.assertFalse(err)
        mock_refresh.assert_not_called()

    def test_cron_skips_refresh_when_valid(self):
        with patch(
            PATH + ".zalo_oapi.refresh_access_token",
            return_value=(
                {"access_token": "AT", "refresh_token": "RT2", "expires_in": "90000"},
                None,
            ),
        ) as mock_refresh:
            self.account._do_refresh(force=True)
            mock_refresh.reset_mock()
            self.env["spa.zalo.oa.account"]._cron_refresh_tokens()
        mock_refresh.assert_not_called()

    # ---------------- booking reminder cron ----------------
    def test_booking_reminder_cron_enqueues(self):
        self._enable_reminder()
        booking = self._make_booking_in_window(self.partner)
        self.env["spa.service.booking"]._cron_send_zalo_reminders()
        self.assertTrue(booking.zalo_reminder_sent)
        msg = self.Message.search(
            [("source_ref", "=", "spa.service.booking,%s" % booking.id)]
        )
        self.assertEqual(len(msg), 1)
        self.assertEqual(msg.event_type, "booking_reminder")
        self.assertEqual(msg.template_id, "tpl_reminder")

    def test_booking_reminder_skips_draft(self):
        self._enable_reminder()
        booking = self._make_booking_in_window(self.partner, state="draft")
        self.env["spa.service.booking"]._cron_send_zalo_reminders()
        self.assertFalse(booking.zalo_reminder_sent)
        self.assertFalse(
            self.Message.search(
                [("source_ref", "=", "spa.service.booking,%s" % booking.id)]
            )
        )

    def test_cancel_booking_cancels_queued_zns(self):
        self._enable_reminder()
        booking = self._make_booking_in_window(self.partner)
        self.env["spa.service.booking"]._cron_send_zalo_reminders()
        msg = self.Message.search(
            [("source_ref", "=", "spa.service.booking,%s" % booking.id)]
        )
        self.assertEqual(msg.state, "queued")
        booking.write({"state": "cancel"})
        self.assertEqual(msg.state, "cancel")

    def test_reschedule_resets_flag_and_cancels_queued(self):
        self._enable_reminder()
        booking = self._make_booking_in_window(self.partner)
        self.env["spa.service.booking"]._cron_send_zalo_reminders()
        msg = self.Message.search(
            [("source_ref", "=", "spa.service.booking,%s" % booking.id)]
        )
        self.assertTrue(booking.zalo_reminder_sent)
        booking.write({"start_datetime": fields.Datetime.now() + timedelta(hours=3)})
        self.assertFalse(booking.zalo_reminder_sent)
        self.assertEqual(msg.state, "cancel")

    def test_template_key_map(self):
        self.ICP.set_param(
            "spa_zalo_oa.reminder_template_keys",
            '{"name": "customer_name", "date": "ngay"}',
        )
        booking = self._make_booking_in_window(self.partner)
        data = booking._zalo_reminder_template_data()
        self.assertIn("customer_name", data)
        self.assertIn("ngay", data)
        self.assertNotIn("name", data)
        self.assertNotIn("service", data)

    # ---------------- whitelist mode ----------------
    def test_whitelist_blocks_non_listed(self):
        self._enable_reminder()
        self.ICP.set_param("spa_zalo_oa.whitelist_enabled", "1")
        self.ICP.set_param("spa_zalo_oa.whitelist_phones", "0911000000")
        booking = self._make_booking_in_window(self.partner)
        self.env["spa.service.booking"]._cron_send_zalo_reminders()
        self.assertFalse(booking.zalo_reminder_sent)
        self.assertFalse(
            self.Message.search(
                [("source_ref", "=", "spa.service.booking,%s" % booking.id)]
            )
        )

    def test_whitelist_allows_listed(self):
        self._enable_reminder()
        self.ICP.set_param("spa_zalo_oa.whitelist_enabled", "1")
        self.ICP.set_param("spa_zalo_oa.whitelist_phones", "0905123456, 0911000000")
        booking = self._make_booking_in_window(self.partner)
        self.env["spa.service.booking"]._cron_send_zalo_reminders()
        self.assertTrue(booking.zalo_reminder_sent)
        msg = self.Message.search(
            [("source_ref", "=", "spa.service.booking,%s" % booking.id)]
        )
        self.assertEqual(len(msg), 1)

    def test_whitelist_disabled_sends_to_all(self):
        self._enable_reminder()
        self.ICP.set_param("spa_zalo_oa.whitelist_enabled", "0")
        self.ICP.set_param("spa_zalo_oa.whitelist_phones", "0911000000")
        booking = self._make_booking_in_window(self.partner)
        self.env["spa.service.booking"]._cron_send_zalo_reminders()
        self.assertTrue(booking.zalo_reminder_sent)

    def test_enqueue_skips_non_whitelist_phone(self):
        self.ICP.set_param("spa_zalo_oa.whitelist_enabled", "1")
        self.ICP.set_param("spa_zalo_oa.whitelist_phones", "0911000000")
        msg = self.Message.enqueue(
            partner=self.partner,
            event_type="booking_reminder",
            template_id="tpl1",
            template_data={},
        )
        self.assertFalse(msg)

    def test_send_fails_when_phone_not_whitelisted(self):
        msg = self.Message.enqueue(
            partner=self.partner,
            event_type="booking_reminder",
            template_id="tpl1",
            template_data={},
        )
        self.assertTrue(msg)
        self.ICP.set_param("spa_zalo_oa.whitelist_enabled", "1")
        self.ICP.set_param("spa_zalo_oa.whitelist_phones", "0911000000")
        with patch(
            PATH + ".zalo_oapi.send_zns", return_value=({"msg_id": "M1"}, None)
        ) as mock_send, patch.object(
            type(self.account), "get_valid_access_token", return_value="tok"
        ):
            self._process_queue()
        self.assertFalse(mock_send.called)
        self.assertEqual(msg.state, "failed")

    def test_booking_reminder_outside_window(self):
        self._enable_reminder()
        self.ICP.set_param("spa_zalo_oa.reminder_offset_value", "2")

        offering = self.env["spa.booking.non_session_offering"].create(
            {"name": "Tư vấn xa", "duration_minutes": 60}
        )
        booking = self.env["spa.service.booking"].create(
            {
                "partner_id": self.partner.id,
                "booking_kind": "non_session",
                "non_session_offering_id": offering.id,
                "start_datetime": fields.Datetime.now() + timedelta(days=5),
                "duration": 60,
            }
        )
        self._confirm_booking(booking)
        self.env["spa.service.booking"]._cron_send_zalo_reminders()
        self.assertFalse(booking.zalo_reminder_sent)
