# -*- coding: utf-8 -*-
"""Gọi Zalo OA Open API: làm mới access_token và gửi tin ZNS theo template.

Dùng urllib (không thêm dependency), trả về (data|None, error_message|None)
giống phong cách spa_zalo/zalo_graph.py.

Tham chiếu Zalo:
- Refresh token: POST https://oauth.zaloapp.com/v4/oa/access_token
  header: secret_key; body x-www-form-urlencoded: refresh_token, app_id, grant_type=refresh_token
- Gửi ZNS:        POST https://business.openapi.zalo.me/message/template
  header: access_token; body JSON: phone, template_id, template_data, tracking_id
"""
import json
import logging
import urllib.error
import urllib.parse
import urllib.request

_logger = logging.getLogger(__name__)

ZALO_OA_TOKEN_URL = "https://oauth.zaloapp.com/v4/oa/access_token"
ZALO_ZNS_SEND_URL = "https://business.openapi.zalo.me/message/template"

DEFAULT_TIMEOUT = 30


def _parse_json(raw):
    try:
        return json.loads(raw) if raw else {}, None
    except json.JSONDecodeError:
        return None, "Phản hồi Zalo không phải JSON"


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
             timeout=DEFAULT_TIMEOUT):
    """Gửi một tin ZNS theo template tới số điện thoại (định dạng 84xxxxxxxxx).

    :param template_data: dict tham số template (vd {"name": "...", "time": "..."}).
    :return: (dict {msg_id, sent_time, quota} | None, error | None)
    """
    if not (access_token or "").strip():
        return None, "Thiếu access_token OA"
    if not (phone or "").strip():
        return None, "Thiếu số điện thoại"
    if not (template_id or "").strip():
        return None, "Thiếu template_id"

    body = {
        "phone": phone.strip(),
        "template_id": str(template_id).strip(),
        "template_data": template_data or {},
    }
    if tracking_id:
        body["tracking_id"] = str(tracking_id)

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
