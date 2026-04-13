# -*- coding: utf-8 -*-
import secrets


def post_init_hook(env):
    """Generate JWT secret once so mini app tokens can be issued securely."""
    icp = env['ir.config_parameter'].sudo()
    if not icp.get_param('troxanh_zmini.jwt_secret'):
        icp.set_param('troxanh_zmini.jwt_secret', secrets.token_urlsafe(48))
