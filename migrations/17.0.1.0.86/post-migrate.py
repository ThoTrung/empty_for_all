# -*- coding: utf-8 -*-
"""Archive legacy per-month 'Tổng thanh toán: MM-YYYY' products.

HSTT total invoices now reuse a single shared 'Tổng thanh toán' service
(models/rental_contract.py:_get_or_create_hstt_total_product) instead of
creating a new product every billing month. Posted invoice lines keep their
original product_id (archived products still display fine on posted moves);
the next invoice creation will create the one canonical product on demand.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    Product = env["product.product"].with_context(active_test=False)

    legacy = Product.search([("name", "=like", "Tổng thanh toán:%")])
    if not legacy:
        return

    legacy.write({"active": False})
    _logger.info(
        "rental 17.0.1.0.86: archived %s legacy monthly 'Tổng thanh toán: MM-YYYY' products",
        len(legacy),
    )
