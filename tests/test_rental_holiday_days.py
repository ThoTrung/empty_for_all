# -*- coding: utf-8 -*-

from datetime import date

from odoo.addons.rental.services import rental_contract_services as rcs
from odoo.tests.common import TransactionCase


class TestRentalHolidayDays(TransactionCase):
    def test_rental_days_without_include_start_and_holiday(self):
        self.env["rental.holiday"].create(
            {
                "name": "Tet 2026",
                "date_from": date(2026, 2, 6),
                "date_to": date(2026, 2, 12),
                "company_id": self.env.company.id,
            }
        )
        # (01 -> 28] = 27 ngày, trừ 7 ngày nghỉ => 20 ngày
        days = rcs.rental_days_between_with_holiday(
            self.env,
            self.env.company,
            date(2026, 2, 1),
            date(2026, 2, 28),
            include_start_day=False,
        )
        self.assertEqual(days, 20)

    def test_rental_days_with_include_start_and_holiday(self):
        self.env["rental.holiday"].create(
            {
                "name": "Tet 2026",
                "date_from": date(2026, 2, 6),
                "date_to": date(2026, 2, 12),
                "company_id": self.env.company.id,
            }
        )
        # [01 -> 28] = 28 ngày, trừ 7 ngày nghỉ => 21 ngày
        days = rcs.rental_days_between_with_holiday(
            self.env,
            self.env.company,
            date(2026, 2, 1),
            date(2026, 2, 28),
            include_start_day=True,
        )
        self.assertEqual(days, 21)
