# -*- coding: utf-8 -*-
"""Nhắc lịch hẹn cho khách hàng qua Zalo ZNS.

Tách biệt với nhắc nhân viên (mail.activity, cờ `reminder_sent`) trong
booking_calendar: dùng cờ riêng `zalo_reminder_sent` để không xung đột.
"""
import json
import logging
from datetime import timedelta

from odoo import api, fields, models

from odoo.addons.spa.helper.duplicate_utils import normalize_phone
from odoo.addons.spa_zalo_oa.models.spa_zalo_message import _icp_is_true

_logger = logging.getLogger(__name__)

DEFAULT_TEMPLATE_KEY_MAP = {
    "name": "name",
    "date": "date",
    "time": "time",
    "service": "service",
}


class SpaServiceBooking(models.Model):
    _inherit = "spa.service.booking"

    zalo_reminder_sent = fields.Boolean(
        string="Đã nhắc KH qua Zalo",
        default=False,
        copy=False,
        index=True,
    )

    def write(self, vals):
        reschedule = self.browse()
        if "start_datetime" in vals:
            new_dt = fields.Datetime.to_datetime(vals["start_datetime"])
            reschedule = self.filtered(lambda b: b.start_datetime != new_dt)
        cancel = self if vals.get("state") == "cancel" else self.browse()
        res = super().write(vals)
        to_drop = reschedule | cancel
        if to_drop:
            to_drop._zalo_cancel_queued_messages()
        if reschedule:
            super(SpaServiceBooking, reschedule).write({"zalo_reminder_sent": False})
        return res

    def _zalo_cancel_queued_messages(self):
        Message = self.env["spa.zalo.message"].sudo()
        for rec in self:
            msgs = Message.search(
                [
                    ("source_ref", "=", "%s,%s" % (rec._name, rec.id)),
                    ("event_type", "=", "booking_reminder"),
                    ("state", "in", ("queued", "failed")),
                ]
            )
            if msgs:
                msgs.action_cancel()

    def _zalo_reminder_offset(self):
        """Khoảng thời gian nhắc trước giờ hẹn, theo cấu hình (đơn vị giờ/ngày)."""
        ICP = self.env["ir.config_parameter"].sudo()
        unit = ICP.get_param("spa_zalo_oa.reminder_offset_unit", "hours")
        try:
            value = int(ICP.get_param("spa_zalo_oa.reminder_offset_value", "2"))
        except (TypeError, ValueError):
            value = 2
        value = max(0, value)
        if unit == "days":
            return timedelta(days=value)
        return timedelta(hours=value)

    def _zalo_template_key_map(self):
        raw = (
            self.env["ir.config_parameter"].sudo().get_param(
                "spa_zalo_oa.reminder_template_keys", ""
            )
            or ""
        ).strip()
        if not raw:
            return dict(DEFAULT_TEMPLATE_KEY_MAP)
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, TypeError, ValueError):
            return dict(DEFAULT_TEMPLATE_KEY_MAP)
        if not isinstance(parsed, dict) or not parsed:
            return dict(DEFAULT_TEMPLATE_KEY_MAP)
        return {
            str(src): str(dest)
            for src, dest in parsed.items()
            if src and dest
        }

    def _zalo_reminder_template_data(self):
        """Tham số template ZNS nhắc lịch.

        Khóa nội bộ: name, date (dd/mm/YYYY), time (HH:MM), service.
        ICP spa_zalo_oa.reminder_template_keys đổi tên 1-1; chỉ gửi khóa đã map.
        """
        self.ensure_one()
        start = self.start_datetime
        local = fields.Datetime.context_timestamp(self, start) if start else None
        service = ""
        product = self._get_display_calendar_service_product()
        if product:
            service = product.display_name
        elif self.non_session_offering_id:
            service = self.non_session_offering_id.display_name
        internal = {
            "name": self.partner_id.name or "",
            "date": local.strftime("%d/%m/%Y") if local else "",
            "time": local.strftime("%H:%M") if local else "",
            "service": service or "",
        }
        mapping = self._zalo_template_key_map()
        return {
            dest: internal[src]
            for src, dest in mapping.items()
            if src in internal
        }

    def _enqueue_zalo_reminder(self):
        """Đưa tin nhắc lịch vào hàng đợi cho các booking trong recordset."""
        ICP = self.env["ir.config_parameter"].sudo()
        template_id = (ICP.get_param("spa_zalo_oa.reminder_template_id", "") or "").strip()
        if not template_id:
            _logger.info("spa_zalo_oa: chưa cấu hình reminder_template_id, bỏ qua.")
            return
        Message = self.env["spa.zalo.message"].sudo()
        for rec in self:
            if rec.zalo_reminder_sent or not rec.partner_id or not rec.start_datetime:
                continue
            msg = Message.enqueue(
                partner=rec.partner_id,
                event_type="booking_reminder",
                template_id=template_id,
                template_data=rec._zalo_reminder_template_data(),
                source_ref="%s,%s" % (rec._name, rec.id),
            )
            # Đánh dấu đã xử lý kể cả khi bị bỏ qua (opt-out / không SĐT) để cron
            # không quét lại booking này mãi.
            rec.zalo_reminder_sent = True
            if not msg:
                _logger.debug(
                    "spa_zalo_oa: bỏ qua nhắc booking %s (opt-out/không SĐT/đã có tin).",
                    rec.id,
                )

    @api.model
    def _zalo_whitelist_phones(self):
        """Tập SĐT (đã chuẩn hóa 84...) được phép nhận tin khi bật chế độ whitelist.

        Trả về `None` khi chế độ whitelist tắt (nghĩa là không giới hạn người nhận).
        """
        ICP = self.env["ir.config_parameter"].sudo()
        if not _icp_is_true(ICP.get_param("spa_zalo_oa.whitelist_enabled", "0")):
            return None
        raw = ICP.get_param("spa_zalo_oa.whitelist_phones", "") or ""
        phones = set()
        for part in raw.replace(";", ",").split(","):
            norm = normalize_phone(part.strip())
            if norm:
                phones.add(norm)
        return phones

    @api.model
    def _cron_send_zalo_reminders(self):
        """Cron: nhắc lịch KH qua Zalo khi lịch đã vào khoảng "trước N giờ/ngày"."""
        ICP = self.env["ir.config_parameter"].sudo()
        if not _icp_is_true(ICP.get_param("spa_zalo_oa.reminder_enabled", "0")):
            return
        now = fields.Datetime.now()
        threshold = now + self._zalo_reminder_offset()
        domain = [
            ("zalo_reminder_sent", "=", False),
            ("state", "=", "confirmed"),
            ("start_datetime", ">", now),
            ("start_datetime", "<=", threshold),
        ]
        bookings = self.search(domain)
        # Chế độ whitelist (test): chỉ gửi SĐT trong danh sách; ngoài danh sách
        # KHÔNG đánh dấu để vẫn nhắc khi chạy thật.
        whitelist = self._zalo_whitelist_phones()
        if whitelist is not None:
            bookings = bookings.filtered(
                lambda b: normalize_phone(
                    b.partner_id.mobile or b.partner_id.phone or ""
                ) in whitelist
            )
            _logger.info(
                "spa_zalo_oa: whitelist bật, còn %s booking khớp danh sách.",
                len(bookings),
            )
        if bookings:
            bookings._enqueue_zalo_reminder()
