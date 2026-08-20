# -*- coding: utf-8 -*-
"""Tài khoản Zalo OA: lưu thông tin app + token và tự làm mới access_token.

Access token OA hết hạn theo `expires_in` (thường ~25h); refresh_token xoay vòng
mỗi lần làm mới (hạn ~3 tháng, dùng 1 lần). Cron + lúc gửi đều có thể refresh:
phải khóa hàng (FOR UPDATE) rồi đọc lại token, nếu không hai tiến trình dùng
cùng refresh_token sẽ làm chết kênh.
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

    def _lock_and_reload(self):
        """Khóa hàng Postgres rồi invalidate để đọc refresh_token mới nhất."""
        self.ensure_one()
        self.env.cr.execute(
            "SELECT id FROM spa_zalo_oa_account WHERE id = %s FOR UPDATE",
            [self.id],
        )
        self.invalidate_recordset()

    def _do_refresh(self, locked=False, force=False):
        """Gọi Zalo đổi token mới; lưu access/refresh/expiry. Trả về error|None.

        :param locked: True nếu caller đã FOR UPDATE.
        :param force: True = gọi API dù token còn hạn (nút thủ công).
        """
        self.ensure_one()
        if not locked:
            self._lock_and_reload()
        if not force and self._token_is_valid():
            return None
        result, err = zalo_oapi.refresh_access_token(
            self.app_id, self.secret_key, self.refresh_token
        )
        if err:
            # Không xóa token cũ: request refresh có thể chưa consume refresh_token.
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
        self._lock_and_reload()
        if self._token_is_valid():
            return self.access_token
        err = self._do_refresh(locked=True)
        if err:
            raise UserError(_("Không lấy được access token Zalo OA: %s") % err)
        return self.access_token

    def action_refresh_token(self):
        """Nút làm mới token thủ công."""
        self.ensure_one()
        err = self._do_refresh(force=True)
        if err:
            raise UserError(_("Làm mới token thất bại: %s") % err)
        return True

    @api.model
    def _cron_refresh_tokens(self):
        """Cron: làm mới access_token sắp hết hạn (bỏ qua nếu còn hạn)."""
        for account in self.search([("active", "=", True), ("refresh_token", "!=", False)]):
            account._lock_and_reload()
            if account._token_is_valid():
                continue
            account._do_refresh(locked=True)
