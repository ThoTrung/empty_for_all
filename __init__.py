# -*- coding: utf-8 -*-

from . import models
from . import wizards


def post_init_hook(env):
    """Safety net: đảm bảo bậc mặc định global tồn tại sau install/upgrade."""
    env["spa.payroll.config"]._spa_ensure_default_tiers(env.company)
