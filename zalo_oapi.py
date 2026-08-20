# -*- coding: utf-8 -*-
"""Gọi Zalo OA Open API: làm mới access_token và gửi tin ZNS theo template.

Dùng urllib (không thêm dependency), trả về (data|None, error_message|None)
giống phong cách spa_zalo/zalo_graph.py.

Tham chiếu Zalo:
- Refresh token: POST https://oauth.zaloapp.com/v4/oa/access_token
  header: secret_key; body x-www-form-urlencoded: refresh_token, app_id, grant_type=refresh_token
  refresh_token dùng 1 lần; response luôn có refresh_token mới.
- Gửi ZNS:        POST https://business.openapi.zalo.me/message/template
  header: access_token; body JSON: phone, template_id, template_data, tracking_id
  tracking_id bắt buộc (Zalo: ≤48 ký tự, không ký tự đặc biệt).
  mode=development: chỉ gửi admin OA/App, không tính phí.
"""
import json
import logging
import re
import urllib.error
import urllib.parse
import urllib.request

from datetime import datetime

import pytz

_logger = logging.getLogger(__name__)

ZALO_OA_TOKEN_URL = "https://oauth.zaloapp.com/v4/oa/access_token"
ZALO_ZNS_SEND_URL = "https://business.openapi.zalo.me/message/template"

DEFAULT_TIMEOUT = 30
VN_TZ = pytz.timezone("Asia/Ho_Chi_Minh")

# Lỗi không bao giờ thành công nếu gửi lại (bảng mã Zalo ZNS).
PERMANENT_ERROR_CODES = frozenset({
    -108, -109, -111, -112, -114, -117, -118, -119,
    -127, -131, -132, -134, -135, -139, -141, -145, -146,
})
# Cấm gửi 22h–6h GMT+7: giữ queued, không tăng retry.
QUIET_HOURS_ERROR_CODE = -133
# Token hết hạn / không hợp lệ: refresh rồi gửi lại một lần.
TOKEN_ERROR_CODES = frozenset({-124, -216, -220, 3})
# Hết quota / ví: dừng lô cron.
STOP_BATCH_ERROR_CODES = frozenset({
    -115, -126, -136, -137, -144, -147,
})

_ERROR_CODE_RE = re.compile(r"\[(-?\d+)\]")


def _parse_json(raw):
    try:
        return json.loads(raw) if raw else {}, None
    except json.JSONDecodeError:
        return None, "Phản hồi Zalo không phải JSON"


def parse_error_code(err):
    """Lấy mã lỗi Zalo từ chuỗi '[code] message'. Không có thì None."""
    if err is None:
        return None
    if isinstance(err, int):
        return err
    match = _ERROR_CODE_RE.search(str(err))
    if not match:
        return None
    try:
        return int(match.group(1))
    except (TypeError, ValueError):
        return None


def sanitize_tracking_id(value):
    """tracking_id ZNS: alphanumeric, tối đa 48 ký tự."""
    raw = re.sub(r"[^A-Za-z0-9]", "", str(value or ""))
    return (raw or "zns")[:48]


def in_zns_quiet_hours(now_utc=None):
    """True trong 22:00–06:00 giờ Việt Nam (Zalo -133)."""
    if now_utc is None:
        now_utc = datetime.utcnow()
    if now_utc.tzinfo is None:
        now_utc = pytz.UTC.localize(now_utc)
    local = now_utc.astimezone(VN_TZ)
    return local.hour >= 22 or local.hour < 6


def refresh_access_token(app_id, secret_key, refresh_token, timeout=DEFAULT_TIMEOUT):
    """Đổi refresh_token lấy access_token mới (và refresh_token mới — Zalo xoay vòng).

    :return: (dict {access_token, refresh_token, expires_in} | None, error | None)
    """
    if not (app_id or "").strip():
        return None, "Thiếu app_id"
    if not (secret_key or "").strip():
        return None, "Thiếu secret_key (App Secret)"
    if not (refresh_token or "").strip():
        return None, "Thiếu refresh_token"

    data = urllib.parse.urlencode(
        {
            "refresh_token": refresh_token.strip(),
            "app_id": app_id.strip(),
            "grant_type": "refresh_token",
        }
    ).encode("utf-8")
    req = urllib.request.Request(ZALO_OA_TOKEN_URL, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    req.add_header("secret_key", secret_key.strip())

    raw = ""
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace") if e.fp else ""
        _logger.warning("Zalo OA token HTTP %s: %s", e.code, raw[:500])
    except urllib.error.URLError as e:
        _logger.warning("Zalo OA token URL error: %s", e)
        return None, "Không kết nối được Zalo OAuth"

    payload, perr = _parse_json(raw)
    if perr:
        return None, perr

    # Zalo trả error/error_name khi thất bại; access_token khi thành công.
    access_token = (payload or {}).get("access_token")
    if not access_token:
        msg = (
            (payload or {}).get("error_description")
            or (payload or {}).get("message")
            or (payload or {}).get("error_name")
            or "Không lấy được access_token"
        )
        return None, str(msg)[:300]

    return {
        "access_token": access_token,
        "refresh_token": (payload or {}).get("refresh_token") or refresh_token,
        "expires_in": (payload or {}).get("expires_in"),
    }, None


def send_zns(access_token, phone, template_id, template_data, tracking_id=None,
             mode=None, timeout=DEFAULT_TIMEOUT):
    """Gửi một tin ZNS theo template tới số điện thoại (định dạng 84xxxxxxxxx).

    :param template_data: dict tham số template (vd {"name": "...", "time": "..."}).
    :param mode: "development" để gửi thử (chỉ admin OA/App); None = production.
    :return: (dict {msg_id, sent_time, quota} | None, error | None)
    """
    if not (access_token or "").strip():
        return None, "Thiếu access_token OA"
    if not (phone or "").strip():
        return None, "Thiếu số điện thoại"
    if not (template_id or "").strip():
        return None, "Thiếu template_id"

    tracking = sanitize_tracking_id(tracking_id)
    body = {
        "phone": phone.strip(),
        "template_id": str(template_id).strip(),
        "template_data": template_data or {},
        "tracking_id": tracking,
    }
    if (mode or "").strip() == "development":
        body["mode"] = "development"

    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(ZALO_ZNS_SEND_URL, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("access_token", access_token.strip())

    raw = ""
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace") if e.fp else ""
        _logger.warning("Zalo ZNS send HTTP %s: %s", e.code, raw[:500])
    except urllib.error.URLError as e:
        _logger.warning("Zalo ZNS send URL error: %s", e)
        return None, "Không kết nối được Zalo ZNS API"

    payload, perr = _parse_json(raw)
    if perr:
        return None, perr

    err = (payload or {}).get("error")
    # error == 0 nghĩa là thành công theo tài liệu Zalo.
    if err not in (0, "0", None):
        msg = (payload or {}).get("message") or "Gửi ZNS thất bại"
        return None, "[%s] %s" % (err, msg)

    info = (payload or {}).get("data") or {}
    return {
        "msg_id": info.get("msg_id") or "",
        "sent_time": info.get("sent_time") or "",
        "quota": info.get("quota") or {},
    }, None
