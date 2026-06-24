# -*- coding: utf-8 -*-
"""Backfill minimum_rental_months (company policy default 2 months) for existing contracts."""


def migrate(cr, version):
    cr.execute(
        """
        UPDATE rental_contract
        SET minimum_rental_months = 2
        WHERE minimum_rental_months IS NULL
        """
    )
