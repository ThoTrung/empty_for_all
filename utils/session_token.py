# -*- coding: utf-8 -*-
"""HMAC-signed session tokens for mini app (no PyJWT dependency)."""
import base64
import hashlib
import hmac
import json
import time


def make_token(user_id, secret, ttl_seconds=604800):
    """Return opaque token string. ttl default 7 days."""
    payload = {'uid': int(user_id), 'exp': int(time.time()) + int(ttl_seconds)}
    body = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(',', ':')).encode()
    ).decode().rstrip('=')
    sig = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    return '%s.%s' % (body, sig)


def read_token(token, secret):
    """Return payload dict with uid and exp, or None if invalid/expired."""
    if not token or not secret or '.' not in token:
        return None
    try:
        body, sig = token.rsplit('.', 1)
        expect = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expect, sig):
            return None
        pad = '=' * (-len(body) % 4)
        payload = json.loads(base64.urlsafe_b64decode(body + pad))
        if payload.get('exp', 0) < int(time.time()):
            return None
        return payload
    except Exception:
        return None
