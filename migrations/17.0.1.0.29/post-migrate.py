# -*- coding: utf-8 -*-
"""Backfill monthly_day_basis = 'calendar' (default) for existing contracts.

Giữ nguyên hành vi cũ (giá ngày = giá tháng / số ngày thực của tháng) cho HĐ hiện có.
"""


def migrate(cr, version):
    cr.execute(
        """
        UPDATE rental_contract
        SET monthly_day_basis = 'calendar'
        WHERE monthly_day_basis IS NULL
        """
    )
