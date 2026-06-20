# -*- coding: utf-8 -*-
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
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
            self.Message._cron_process_queue()
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
            self.Message._cron_process_queue()
            self.assertEqual(msg.state, "queued")
            self.assertEqual(msg.retry_count, 1)
            self.Message._cron_process_queue()
        self.assertEqual(msg.state, "failed")
        self.assertEqual(msg.retry_count, 2)

    # ---------------- token refresh ----------------
    def test_token_refresh(self):
        with patch(
            PATH + ".zalo_oapi.refresh_access_token",
            return_value=(
                {"access_token": "AT", "refresh_token": "RT2", "expires_in": "90000"},
                None,
            ),
        ):
            err = self.account._do_refresh()
        self.assertFalse(err)
        self.assertEqual(self.account.access_token, "AT")
        self.assertEqual(self.account.refresh_token, "RT2")
        self.assertTrue(self.account._token_is_valid())

    # ---------------- booking reminder cron ----------------
    def test_booking_reminder_cron_enqueues(self):
        self.ICP.set_param("spa_zalo_oa.reminder_enabled", "1")
        self.ICP.set_param("spa_zalo_oa.reminder_template_id", "tpl_reminder")
        self.ICP.set_param("spa_zalo_oa.reminder_offset_unit", "hours")
        self.ICP.set_param("spa_zalo_oa.reminder_offset_value", "48")

        offering = self.env["spa.booking.non_session_offering"].create(
            {"name": "Tư vấn", "duration_minutes": 60}
        )
        booking = self.env["spa.service.booking"].create(
            {
                "partner_id": self.partner.id,
                "booking_kind": "non_session",
                "non_session_offering_id": offering.id,
                "start_datetime": fields.Datetime.now() + timedelta(hours=2),
                "duration": 60,
            }
        )
        self.env["spa.service.booking"]._cron_send_zalo_reminders()
        self.assertTrue(booking.zalo_reminder_sent)
        msg = self.Message.search(
            [("source_ref", "=", "spa.service.booking,%s" % booking.id)]
        )
        self.assertEqual(len(msg), 1)
        self.assertEqual(msg.event_type, "booking_reminder")
        self.assertEqual(msg.template_id, "tpl_reminder")

    def test_booking_reminder_outside_window(self):
        self.ICP.set_param("spa_zalo_oa.reminder_enabled", "1")
        self.ICP.set_param("spa_zalo_oa.reminder_template_id", "tpl_reminder")
        self.ICP.set_param("spa_zalo_oa.reminder_offset_unit", "hours")
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
        self.env["spa.service.booking"]._cron_send_zalo_reminders()
        self.assertFalse(booking.zalo_reminder_sent)
