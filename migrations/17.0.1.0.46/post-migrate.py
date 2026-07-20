# -*- coding: utf-8 -*-
"""Transient as-of quantity models require no persistent-data backfill."""


def migrate(cr, version):
    # Odoo creates the transient wizard tables during the module upgrade.
    pass
