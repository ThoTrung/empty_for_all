# -*- coding: utf-8 -*-
from datetime import date

from odoo.addons.rental.services import rental_contract_services as rcs
from odoo.tests.common import TransactionCase


class TestRentalBillingScenarios(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        company = cls.env.company
        cls._a_company = cls.env["res.partner"].create({
            "name": "Billing Test Renter",
            "is_company": True,
            "customer_type": "renter",
        })
        cls._a_party = cls.env["res.partner"].create({
            "name": "Billing A rep",
            "parent_id": cls._a_company.id,
        })
        cls._b_party = cls.env["res.partner"].create({
            "name": "Billing B rep",
            "parent_id": company.partner_id.id,
        })
        cls._driver = cls.env["res.partner"].create({
            "name": "Billing Driver",
            "customer_type": "driver",
        })
        cls._truck = cls.env["transport.truck"].create({
            "plate": "51A-00001", "name": "51A-00001", "company_id": company.id,
        })
        # single-variant product => effective monthly price == contract line price_unit
        cls._product = cls.env["product.product"].create({
            "name": "Giàn giáo A", "type": "product", "list_price": 2500.0,
        })
        cls._contract = cls.env["rental.contract"].create({
            "a_company_party": cls._a_company.id,
            "a_party": cls._a_party.id,
            "b_company_party": company.partner_id.id,
            "b_party": cls._b_party.id,
            "rental_billing_mode": "month",
            "minimum_rental_months": 2,
        })
        cls._line = cls.env["rental.contract.line"].create({
            "contract_id": cls._contract.id,
            "product_tmpl_id": cls._product.product_tmpl_id.id,
            "price_unit": 2500.0,
        })

    def _make_transport(self, ttype, when, lines):
        """lines: list of (product, qty, non_billable_qty)."""
        return self.env["rr.transport"].create({
            "rental_contract_id": self._contract.id,
            "type": ttype,
            "start_rental_or_return_date": when,
            "driver_id": self._driver.id,
            "transport_truck_id": self._truck.id,
            "vehicle_start_time": when,
            "transport_line_ids": [
                (0, 0, {"product_id": p.id, "qty": q, "non_billable_qty": nb})
                for (p, q, nb) in lines
            ],
        })

    # ----- Scenario 1: effective-dated price -----
    def test_effective_price_changes_over_time(self):
        self.env["rental.contract.line.price"].create({
            "contract_line_id": self._line.id,
            "date_from": date(2026, 2, 1),
            "price_unit": 2400.0,
        })
        self.assertEqual(self._line._effective_price_unit(date(2026, 1, 15)), 2500.0)
        self.assertEqual(self._line._effective_price_unit(date(2026, 2, 15)), 2400.0)
        self.assertEqual(self._line._effective_price_unit(None), 2500.0)

        tmpl_id = self._product.product_tmpl_id.id
        ratio_jan = rcs.contract_line_ratios_by_template(self._contract, date(2026, 1, 31))
        ratio_feb = rcs.contract_line_ratios_by_template(self._contract, date(2026, 2, 28))
        # ratio = effective_price / list_price (2500)
        self.assertAlmostEqual(ratio_jan[tmpl_id], 1.0)
        self.assertAlmostEqual(ratio_feb[tmpl_id], 2400.0 / 2500.0)

    def test_billing_uses_effective_price(self):
        self.env["rental.contract.line.price"].create({
            "contract_line_id": self._line.id,
            "date_from": date(2026, 2, 1),
            "price_unit": 2400.0,
        })
        self._make_transport("delivery", date(2026, 1, 1), [(self._product, 100, 0)])

        jan = rcs._build_map_product_and_date_to_line(
            self.env, self._contract, date(2026, 1, 1), date(2026, 1, 31)
        )
        feb = rcs._build_map_product_and_date_to_line(
            self.env, self._contract, date(2026, 2, 1), date(2026, 2, 28)
        )
        jan_price = list(jan.values())[0]["unit_price"]
        feb_price = list(feb.values())[0]["unit_price"]
        # month mode: unit_price = monthly_effective / days_in_month
        self.assertAlmostEqual(jan_price, 2500.0 / 31)
        self.assertAlmostEqual(feb_price, 2400.0 / 28)

    # ----- Scenario 2: minimum period + LIFO matching -----
    def test_lifo_match_single_lot_early_return(self):
        self._make_transport("delivery", date(2026, 1, 1), [(self._product, 2000, 0)])
        self._make_transport("delivery", date(2026, 1, 20), [(self._product, 1000, 0)])
        self._make_transport("delivery", date(2026, 5, 1), [(self._product, 3000, 0)])
        self._make_transport("return", date(2026, 5, 20), [(self._product, 2000, 0)])

        events = rcs._build_billing_events(self.env, self._contract, date(2026, 12, 31))
        returns = [e for e in events if e["qty"] < 0]
        self.assertEqual(len(returns), 1)
        # matched LIFO to May 1 lot; min 2 months -> effective return Jul 1
        self.assertEqual(returns[0]["qty"], -2000)
        self.assertEqual(returns[0]["date"], date(2026, 7, 1))

    def test_lifo_match_spanning_multiple_lots(self):
        self._make_transport("delivery", date(2026, 1, 1), [(self._product, 2000, 0)])
        self._make_transport("delivery", date(2026, 1, 20), [(self._product, 1000, 0)])
        self._make_transport("delivery", date(2026, 5, 1), [(self._product, 3000, 0)])
        self._make_transport("return", date(2026, 5, 20), [(self._product, 4000, 0)])

        events = rcs._build_billing_events(self.env, self._contract, date(2026, 12, 31))
        returns = sorted([e for e in events if e["qty"] < 0], key=lambda e: e["date"])
        # 1000 from Jan 20 lot (already > 2 months -> actual May 20)
        self.assertEqual(returns[0]["date"], date(2026, 5, 20))
        self.assertEqual(returns[0]["qty"], -1000)
        # 3000 from May 1 lot (early -> minimum Jul 1)
        self.assertEqual(returns[1]["date"], date(2026, 7, 1))
        self.assertEqual(returns[1]["qty"], -3000)

    def test_minimum_disabled_returns_actual_date(self):
        self._contract.minimum_rental_months = 0
        self._make_transport("delivery", date(2026, 5, 1), [(self._product, 3000, 0)])
        self._make_transport("return", date(2026, 5, 20), [(self._product, 3000, 0)])
        events = rcs._build_billing_events(self.env, self._contract, date(2026, 12, 31))
        returns = [e for e in events if e["qty"] < 0]
        self.assertEqual(returns[0]["date"], date(2026, 5, 20))

    def test_line_minimum_overrides_contract(self):
        self._line.minimum_rental_months = 1
        self._make_transport("delivery", date(2026, 5, 1), [(self._product, 1000, 0)])
        self._make_transport("return", date(2026, 5, 10), [(self._product, 1000, 0)])
        events = rcs._build_billing_events(self.env, self._contract, date(2026, 12, 31))
        returns = [e for e in events if e["qty"] < 0]
        # override = 1 month -> effective return Jun 1
        self.assertEqual(returns[0]["date"], date(2026, 6, 1))

    # ----- Scenario 3: excess (non-billable) quantity -----
    def test_excess_qty_not_billed(self):
        self._make_transport("delivery", date(2026, 3, 1), [(self._product, 2000, 1000)])
        bob, cur = rcs.calc_rental_payment_table_grouped_by_template(
            self.env, self._contract, date(2026, 3, 1), date(2026, 3, 31)
        )
        merged = {**bob, **cur}
        tmpl_id = self._product.product_tmpl_id.id
        self.assertIn(tmpl_id, merged)
        # billable = 2000 - 1000 = 1000
        self.assertEqual(merged[tmpl_id]["total_qty"], 1000)

    def test_fully_excess_line_skipped(self):
        self._make_transport("delivery", date(2026, 3, 1), [(self._product, 500, 500)])
        events = rcs._build_billing_events(self.env, self._contract, date(2026, 3, 31))
        self.assertFalse(events)
