# -*- coding: utf-8 -*-
"""Stamp action/menu title: Lịch sử chuyến xe (fix vi_VN override)."""


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    action = env.ref("rental.action_rr_transport", raise_if_not_found=False)
    if not action:
        return
    # Clear per-lang overrides (e.g. vi_VN still "Xuất nhập kho") then set once.
    action.with_context(lang=None).write({"name": "Lịch sử chuyến xe"})
    for lang in env["res.lang"].search([("active", "=", True)]).mapped("code"):
        action.with_context(lang=lang).write({"name": "Lịch sử chuyến xe"})
