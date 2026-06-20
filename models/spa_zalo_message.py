# -*- coding: utf-8 -*-
"""Hàng đợi / nhật ký tin ZNS gửi cho khách hàng.

Mọi tin được tạo ở trạng thái `queued` rồi cron gửi theo lô: tránh chặn luồng
nghiệp vụ, có retry khi lỗi, có audit, và tôn trọng quota/giới hạn của Zalo.
"""
import json
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.spa.helper.duplicate_utils import normalize_phone
from odoo.addons.spa_zalo_oa import zalo_oapi

_logger = logging.getLogger(__name__)

DEFAULT_MAX_RETRY = 3
DEFAULT_BATCH_SIZE = 50


class SpaZaloMessage(models.Model):
    _name = "spa.zalo.message"
    _description = "Tin Zalo ZNS gửi khách hàng"
    _order = "id desc"

    name = fields.Char(string="Tham chiếu", readonly=True, copy=False, default="/")
    partner_id = fields.Many2one(
        "res.partner", string="Khách hàng", ondelete="cascade", index=True
    )
    phone = fields.Char(string="SĐT (84...)", required=True, index=True)
    event_type = fields.Selection(
        selection=[
            ("booking_reminder", "Nhắc lịch hẹn"),
            ("booking_confirm", "Xác nhận đặt lịch"),
            ("birthday", "Chúc mừng sinh nhật"),
            ("session_done", "Cảm ơn sau buổi trị liệu"),
            ("promo", "Khuyến mãi"),
            ("other", "Khác"),
        ],
        string="Loại sự kiện",
        default="other",
        required=True,
        index=True,
    )
    template_id = fields.Char(string="ZNS Template ID", required=True)
    template_data_json = fields.Text(
        string="Tham số template (JSON)",
        default="{}",
        help="Map tham số template ZNS, vd: {\"name\": \"...\", \"time\": \"...\"}",
    )
    state = fields.Selection(
        selection=[
            ("queued", "Chờ gửi"),
            ("sent", "Đã gửi"),
            ("failed", "Thất bại"),
            ("cancel", "Đã hủy"),
        ],
        string="Trạng thái",
        default="queued",
        required=True,
        index=True,
    )
    zalo_msg_id = fields.Char(string="Mã tin Zalo", copy=False, readonly=True)
    error = fields.Char(string="Lỗi", copy=False, readonly=True)
    retry_count = fields.Integer(string="Số lần thử lại", default=0, copy=False)
    sent_date = fields.Datetime(string="Thời điểm gửi", copy=False, readonly=True)
    # Tham chiếu nguồn (chống tạo trùng), vd "spa.service.booking,12".
    source_ref = fields.Char(string="Nguồn", index=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name") or vals.get("name") == "/":
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code("spa.zalo.message") or "/"
                )
        return super().create(vals_list)

    def _template_data(self):
        self.ensure_one()
        try:
            data = json.loads(self.template_data_json or "{}")
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}

    @api.model
    def _max_retry(self):
        try:
            return int(
                self.env["ir.config_parameter"].sudo().get_param(
                    "spa_zalo_oa.max_retry", DEFAULT_MAX_RETRY
                )
            )
        except (TypeError, ValueError):
            return DEFAULT_MAX_RETRY

    @api.model
    def enqueue(self, partner, event_type, template_id, template_data,
                phone=None, source_ref=None):
        """Tạo một tin ở trạng thái chờ gửi.

        Trả về record đã tạo, hoặc empty recordset nếu bị bỏ qua (opt-out,
        không có SĐT, thiếu template, hoặc đã tồn tại cho source_ref).
        """
        empty = self.browse()
        if partner and partner.zalo_optout:
            return empty
        raw_phone = phone or (partner.mobile or partner.phone if partner else "")
        norm = normalize_phone(raw_phone or "")
        if not norm:
            return empty
        if not (template_id or "").strip():
            return empty
        if source_ref:
            existing = self.search(
                [
                    ("source_ref", "=", source_ref),
                    ("event_type", "=", event_type),
                    ("state", "!=", "cancel"),
                ],
                limit=1,
            )
            if existing:
                return empty
        return self.create(
            {
                "partner_id": partner.id if partner else False,
                "phone": norm,
                "event_type": event_type,
                "template_id": template_id,
                "template_data_json": json.dumps(template_data or {}, ensure_ascii=False),
                "source_ref": source_ref or False,
                "state": "queued",
            }
        )

    def _send_one(self, access_token):
        """Gửi một tin với access_token cho trước; cập nhật trạng thái."""
        self.ensure_one()
        result, err = zalo_oapi.send_zns(
            access_token,
            self.phone,
            self.template_id,
            self._template_data(),
            tracking_id=self.name,
        )
        if err:
            retry = self.retry_count + 1
            new_state = "failed" if retry >= self._max_retry() else "queued"
            self.write({"retry_count": retry, "error": err, "state": new_state})
            return False
        self.write(
            {
                "state": "sent",
                "zalo_msg_id": result.get("msg_id") or "",
                "sent_date": fields.Datetime.now(),
                "error": False,
            }
        )
        return True

    def action_send_now(self):
        account = self.env["spa.zalo.oa.account"]._get_default()
        if not account:
            raise UserError(_("Chưa cấu hình tài khoản Zalo OA."))
        token = account.get_valid_access_token()
        for msg in self.filtered(lambda m: m.state in ("queued", "failed")):
            msg._send_one(token)
        return True

    def action_retry(self):
        self.filtered(lambda m: m.state == "failed").write(
            {"state": "queued", "retry_count": 0, "error": False}
        )
        return True

    def action_cancel(self):
        self.filtered(lambda m: m.state in ("queued", "failed")).write({"state": "cancel"})
        return True

    @api.model
    def _cron_process_queue(self):
        """Cron: gửi các tin đang chờ theo lô."""
        account = self.env["spa.zalo.oa.account"]._get_default()
        if not account:
            _logger.info("spa_zalo_oa: chưa cấu hình OA, bỏ qua hàng đợi ZNS.")
            return
        try:
            batch = int(
                self.env["ir.config_parameter"].sudo().get_param(
                    "spa_zalo_oa.batch_size", DEFAULT_BATCH_SIZE
                )
            )
        except (TypeError, ValueError):
            batch = DEFAULT_BATCH_SIZE
        messages = self.search([("state", "=", "queued")], limit=batch, order="id asc")
        if not messages:
            return
        try:
            token = account.get_valid_access_token()
        except UserError as e:
            _logger.warning("spa_zalo_oa: không lấy được token OA: %s", e)
            return
        for msg in messages:
            msg._send_one(token)
