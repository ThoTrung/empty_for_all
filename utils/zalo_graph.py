# -*- coding: utf-8 -*-
"""Verify Zalo Mini App getPhoneNumber payload on the server (Zalo Graph API)."""
import json
import logging
import urllib.error
import urllib.request

from odoo.addons.aitilen.tools.portal_phone import normalize_phone_vn_zalo

_logger = logging.getLogger(__name__)

ZALO_ME_INFO_URL = 'https://graph.zalo.me/v2.0/me/info'


def fetch_zalo_verified_phone_number(secret_key, access_token, code):
    """
    Exchange mini-app access_token + code (from getPhoneNumber) for the user's phone.

    Headers follow Zalo Mini App server-side documentation.
    Returns normalized VN phone (84...) or None.
    """
    if not secret_key or not access_token or not code:
        return None
    req = urllib.request.Request(
        ZALO_ME_INFO_URL,
        method='GET',
        headers={
            'access_token': access_token,
            'code': code,
            'secret_key': secret_key,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode()
        data = json.loads(raw)
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors='replace') if e.fp else ''
        _logger.warning('Zalo graph HTTPError %s: %s', e.code, body)
        return None
    except Exception as e:
        _logger.warning('Zalo graph request failed: %s', e)
        return None

    number = data.get('number')
    if number is None and isinstance(data.get('data'), dict):
        number = data['data'].get('number')
    if not number:
        return None
    return normalize_phone_vn_zalo(str(number)) or None
