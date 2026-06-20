# -*- coding: utf-8 -*-
"""Tài khoản Zalo OA: lưu thông tin app + token và tự làm mới access_token.

Access token OA hết hạn ~25h; refresh_token xoay vòng mỗi lần làm mới
(hạn ~3 tháng). Vì vậy cần cron làm mới định kỳ, nếu không kênh gửi sẽ chết.
"""
import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.spa_zalo_oa import zalo_oapi

_logger = logging.getLogger(__name__)

# Làm mới sớm trước khi hết hạn để tránh khoảng trống token.
TOKEN_REFRESH_SKEW_SECONDS = 3600


class SpaZaloOaAccount(models.Model):
    _name = "spa.zalo.oa.account"
    _description = "Tài khoản Zalo OA (gửi ZNS)"
    _order = "id desc"

    name = fields.Char(string="Tên", required=True, default="Zalo OA")
    active = fields.Boolean(default=True)
    app_id = fields.Char(string="App ID", required=True)
    secret_key = fields.Char(string="App Secret", required=True)
    oa_id = fields.Char(string="OA ID", help="ID Official Account (tham khảo).")
    access_token = fields.Char(string="Access Token", copy=False)
    refresh_token = fields.Char(string="Refresh Token", copy=False)
    token_expiry = fields.Datetime(string="Hết hạn access token", copy=False)
    last_refresh = fields.Datetime(string="Lần làm mới gần nhất", copy=False, readonly=True)
    last_error = fields.Char(string="Lỗi gần nhất", copy=False, readonly=True)

    @api.model
    def _get_default(self):
        """Tài khoản OA đang dùng (active, mới nhất). Có thể không tồn tại."""
        return self.search([("active", "=", True)], limit=1)

    def _token_is_valid(self):
        self.ensure_one()
        if not self.access_token or not self.token_expiry:
            return False
        skew = timedelta(seconds=TOKEN_REFRESH_SKEW_SECONDS)
        return fields.Datetime.now() + skew < self.token_expiry

    def _do_refresh(self):
        """Gọi Zalo đổi token mới; lưu access/refresh/expiry. Trả về error|None."""
        self.ensure_one()
        result, err = zalo_oapi.refresh_access_token(
            self.app_id, self.secret_key, self.refresh_token
        )
        if err:
            self.sudo().write({"last_error": err})
            _logger.warning("Zalo OA %s refresh lỗi: %s", self.id, err)
            return err
        try:
            expires_in = int(result.get("expires_in") or 0)
        except (TypeError, ValueError):
            expires_in = 0
        vals = {
            "access_token": result["access_token"],
            "refresh_token": result["refresh_token"],
            "last_refresh": fields.Datetime.now(),
            "last_error": False,
        }
        if expires_in > 0:
            vals["token_expiry"] = fields.Datetime.now() + timedelta(seconds=expires_in)
        self.sudo().write(vals)
        return None

    def get_valid_access_token(self):
        """Trả về access_token còn hạn (tự làm mới nếu cần). Raise nếu không lấy được."""
        self.ensure_one()
        if self._token_is_valid():
            return self.access_token
        err = self._do_refresh()
        if err:
            raise UserError(_("Không lấy được access token Zalo OA: %s") % err)
        return self.access_token

    def action_refresh_token(self):
        """Nút làm mới token thủ công."""
        self.ensure_one()
        err = self._do_refresh()
        if err:
            raise UserError(_("Làm mới token thất bại: %s") % err)
        return True

    @api.model
    def _cron_refresh_tokens(self):
        """Cron: làm mới access_token cho mọi tài khoản OA đang dùng."""
        for account in self.search([("active", "=", True), ("refresh_token", "!=", False)]):
            account._do_refresh()
