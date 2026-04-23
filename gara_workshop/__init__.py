# -*- coding: utf-8 -*-

from . import models
from . import wizards


def post_init_hook(env):
    """Ensure repair picking types exist on all warehouses (same as repair module hook)."""
    from odoo.addons.repair import _create_warehouse_data
    _create_warehouse_data(env)
    env['res.company'].gara_apply_vn_product_defaults_all_companies()
