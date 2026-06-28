# -*- coding: utf-8 -*-
"""Nhắc lịch hẹn cho khách hàng qua Zalo ZNS.

Tách biệt với nhắc nhân viên (mail.activity, cờ `reminder_sent`) trong
booking_calendar: dùng cờ riêng `zalo_reminder_sent` để không xung đột.
"""
import logging
from datetime import timedelta

from odoo import api, fields, models

from odoo.addons.spa.helper.duplicate_utils import normalize_phone

_logger = logging.getLogger(__name__)


class SpaServiceBooking(models.Model):
    _inherit = "spa.service.booking"

    zalo_reminder_sent = fields.Boolean(
        string="Đã nhắc KH qua Zalo",
        default=False,
        copy=False,
        index=True,
    )

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

    def _zalo_reminder_template_data(self):
        """Tham số mặc định cho template ZNS nhắc lịch.

        Tên tham số phải khớp template đã duyệt trên Zalo. Mặc định dùng
        các khóa phổ biến; điều chỉnh theo template thực tế của bạn.
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
        return {
            "name": self.partner_id.name or "",
            "date": local.strftime("%d/%m/%Y") if local else "",
            "time": local.strftime("%H:%M") if local else "",
            "service": service or "",
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
        if ICP.get_param("spa_zalo_oa.whitelist_enabled", "0") != "1":
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
        if ICP.get_param("spa_zalo_oa.reminder_enabled", "0") != "1":
            return
        now = fields.Datetime.now()
        threshold = now + self._zalo_reminder_offset()
        domain = [
            ("zalo_reminder_sent", "=", False),
            ("state", "in", ["draft", "confirmed"]),
            ("start_datetime", ">", now),
            ("start_datetime", "<=", threshold),
        ]
        bookings = self.search(domain)
        # Chế độ whitelist (test trên production): chỉ gửi cho các SĐT trong danh
        # sách; booking ngoài danh sách KHÔNG được đánh dấu để vẫn nhắc khi chạy thật.
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
