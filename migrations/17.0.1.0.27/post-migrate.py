# -*- coding: utf-8 -*-
"""Backfill minimum_rental_billing_mode = 'upfront' (default) for existing contracts."""


def migrate(cr, version):
    cr.execute(
        """
        UPDATE rental_contract
        SET minimum_rental_billing_mode = 'upfront'
        WHERE minimum_rental_billing_mode IS NULL
        """
    )
