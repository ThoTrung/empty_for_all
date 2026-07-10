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

    # ----- Scenario 4: minimum period billed up-front in the return month (default) -----
    def test_upfront_same_month_return_bills_full_minimum(self):
        # Default mode = 'upfront'. Deliver 80 on Jun 10, return 30 on Jun 20, min 2 months.
        self.assertEqual(self._contract.minimum_rental_billing_mode, "upfront")
        self._make_transport("delivery", date(2026, 6, 10), [(self._product, 80, 0)])
        self._make_transport("return", date(2026, 6, 20), [(self._product, 30, 0)])

        jun = rcs._build_map_product_and_date_to_line(
            self.env, self._contract, date(2026, 6, 1), date(2026, 6, 30)
        )
        by_end = {l["end_date"]: l for l in jun.values()}
        self.assertEqual(set(by_end), {date(2026, 6, 30), date(2026, 8, 9)})
        # 50 still rented -> normal until end of June
        normal = by_end[date(2026, 6, 30)]
        self.assertEqual(normal["qty"], 50)
        self.assertEqual(normal["rental_days"], 20)  # Jun 10 -> Jun 30
        # 30 returned -> billed to the last day of the minimum period
        # (Jun 10 + 2 months - 1 day = Aug 9), all settled in the June table.
        settled = by_end[date(2026, 8, 9)]
        self.assertEqual(settled["qty"], 30)
        self.assertEqual(settled["start_date"], date(2026, 6, 10))
        self.assertEqual(settled["rental_days"], 60)  # Jun 10 -> Aug 9 (handover day excluded)

        # July table: the 30 returned are already settled; only the 50 still out remain.
        jul = rcs._build_map_product_and_date_to_line(
            self.env, self._contract, date(2026, 7, 1), date(2026, 7, 31)
        )
        self.assertEqual(sum(l["qty"] for l in jul.values()), 50)
        self.assertTrue(all(l["end_date"] == date(2026, 7, 31) for l in jul.values()))

    def test_upfront_next_month_return_settles_remaining_minimum(self):
        # Deliver 80 on Jun 10, return 30 on Jul 10 (after June), min 2 months -> min_end Aug 10.
        self._make_transport("delivery", date(2026, 6, 10), [(self._product, 80, 0)])
        self._make_transport("return", date(2026, 7, 10), [(self._product, 30, 0)])

        # June: nothing returned yet -> all 80 billed normally.
        jun = rcs._build_map_product_and_date_to_line(
            self.env, self._contract, date(2026, 6, 1), date(2026, 6, 30)
        )
        self.assertEqual(len(jun), 1)
        self.assertEqual(list(jun.values())[0]["qty"], 80)

        # July: 50 still out (normal to Jul 31) + 30 returned billed Jul 1 -> Aug 10.
        jul = rcs._build_map_product_and_date_to_line(
            self.env, self._contract, date(2026, 7, 1), date(2026, 7, 31)
        )
        by_end = {l["end_date"]: l for l in jul.values()}
        self.assertEqual(by_end[date(2026, 7, 31)]["qty"], 50)
        settled = by_end[date(2026, 8, 9)]
        self.assertEqual(settled["qty"], 30)
        self.assertEqual(settled["start_date"], date(2026, 7, 1))

        # August: returned 30 already settled in July -> only the 50 still out remain.
        aug = rcs._build_map_product_and_date_to_line(
            self.env, self._contract, date(2026, 8, 1), date(2026, 8, 31)
        )
        self.assertEqual(sum(l["qty"] for l in aug.values()), 50)

    def test_upfront_delivery_on_first_day_is_current_and_minimum_last_day(self):
        # Issue 1: delivered exactly on the period's first day -> "Thuê kỳ này", not "Dư đầu kỳ".
        # Issue 2: 2-month minimum from Jun 1 ends on Jul 31 (the last day), not Aug 1.
        self._make_transport("delivery", date(2026, 6, 1), [(self._product, 80, 0)])
        self._make_transport("return", date(2026, 6, 15), [(self._product, 40, 0)])

        jun = rcs._build_map_product_and_date_to_line(
            self.env, self._contract, date(2026, 6, 1), date(2026, 6, 30)
        )
        # None of the lines are "Dư đầu kỳ".
        self.assertTrue(all(not l["is_bob"] for l in jun.values()))
        by_end = {l["end_date"]: l for l in jun.values()}
        self.assertEqual(set(by_end), {date(2026, 6, 30), date(2026, 7, 31)})
        self.assertEqual(by_end[date(2026, 6, 30)]["qty"], 40)
        settled = by_end[date(2026, 7, 31)]
        self.assertEqual(settled["qty"], 40)
        self.assertEqual(settled["start_date"], date(2026, 6, 1))
        # Opening day is billed (delivered on/before the period start): 2 months = 61 days.
        self.assertEqual(settled["rental_days"], 61)  # Jun 1 -> Jul 31

        # Table sections: everything sits under "Thuê kỳ này", nothing under "Dư đầu kỳ".
        bob, cur = rcs.calc_rental_payment_table_grouped_by_template(
            self.env, self._contract, date(2026, 6, 1), date(2026, 6, 30)
        )
        self.assertFalse(bob)
        self.assertTrue(cur)

    def test_upfront_lines_grouped_by_delivery_reconcile(self):
        # Ex2: deliveries 100 (Jun 10) + 60 (Jun 15); returns 80 (Jun 20) + 70 (Jun 25).
        self._make_transport("delivery", date(2026, 6, 10), [(self._product, 100, 0)])
        self._make_transport("delivery", date(2026, 6, 15), [(self._product, 60, 0)])
        self._make_transport("return", date(2026, 6, 20), [(self._product, 80, 0)])
        self._make_transport("return", date(2026, 6, 25), [(self._product, 70, 0)])
        lines = list(
            rcs._build_map_product_and_date_to_line(
                self.env, self._contract, date(2026, 6, 1), date(2026, 6, 30)
            ).values()
        )
        # Each delivery lot reconciles with the delivered quantity.
        by_lot = {}
        for l in lines:
            by_lot.setdefault(l["deliver_date"], 0)
            by_lot[l["deliver_date"]] += l["qty"]
        self.assertEqual(by_lot[date(2026, 6, 10)], 100)
        self.assertEqual(by_lot[date(2026, 6, 15)], 60)
        # Lot Jun 10: 10 still rented + 90 returned early (penalty), split by return date.
        jun10 = [l for l in lines if l["deliver_date"] == date(2026, 6, 10)]
        self.assertEqual(sum(l["qty"] for l in jun10 if l["kind"] == "present"), 10)
        minimum10 = [l for l in jun10 if l["kind"] == "minimum"]
        self.assertEqual(sum(l["qty"] for l in minimum10), 90)
        self.assertEqual(
            {l["return_date"] for l in minimum10}, {date(2026, 6, 20), date(2026, 6, 25)}
        )
        # Lot Jun 15: fully returned early.
        jun15 = [l for l in lines if l["deliver_date"] == date(2026, 6, 15)]
        self.assertTrue(all(l["kind"] == "minimum" for l in jun15))
        self.assertEqual(sum(l["qty"] for l in jun15), 60)

    def test_payment_blocks_layout_matches_mockup(self):
        # Theo ảnh nhân viên: tồn 2.000 (thuê cả kỳ) + giao 1.400/1.076, trả 1.650/700.
        self._make_transport("delivery", date(2026, 3, 15), [(self._product, 2000, 0)])
        self._make_transport("delivery", date(2026, 4, 5), [(self._product, 1400, 0)])
        self._make_transport("delivery", date(2026, 4, 6), [(self._product, 1076, 0)])
        self._make_transport("return", date(2026, 4, 27), [(self._product, 1650, 0)])
        self._make_transport("return", date(2026, 4, 28), [(self._product, 700, 0)])
        blocks = rcs.calc_rental_payment_blocks_by_template(
            self.env, self._contract, date(2026, 4, 1), date(2026, 4, 30)
        )
        self.assertEqual(len(blocks), 1)
        block = blocks[0]
        # Phần 1: chỉ lô tồn 2.000 (không bị trả) là đơn thuê bình thường.
        self.assertEqual(sum(l["qty"] for l in block["normal_lines"]), 2000)
        rc = block["return_calc"]
        self.assertIsNotNone(rc)
        # Sub-block A: lô đối ứng = 1.400 (05/04) + 1.076 (06/04); trả gộp theo ngày.
        self.assertEqual(
            {(o["date"], o["qty"]) for o in rc["offset_deliveries"]},
            {(date(2026, 4, 5), 1400), (date(2026, 4, 6), 1076)},
        )
        self.assertEqual(
            {(r["date"], r["qty"]) for r in rc["returns"]},
            {(date(2026, 4, 27), 1650), (date(2026, 4, 28), 700)},
        )
        # Sub-block B: phần dư còn thuê 126 (lô 05/04) + phần phạt 2.350.
        self.assertEqual(sum(l["qty"] for l in rc["leftover_present"]), 126)
        self.assertEqual(sum(a["qty"] for a in rc["penalty_rows"]), 2350)
        self.assertFalse(rc["returned_rows"])  # tất cả đều bị phạt
        # Cộng đang thuê cuối kỳ = 2.000 + 126 = 2.126.
        self.assertEqual(block["present_total_qty"], 2126)

    def test_payment_blocks_merge_bob_and_exact_offset(self):
        # Nhiều lô dư đầu kỳ (cùng hiển thị 01->30) phải gộp 1 dòng; trả đối ứng dư
        # đầu kỳ chỉ tách đúng số lượng cần lấy, phần còn lại vẫn nằm ở dư đầu kỳ.
        for d, q in [(15, 500), (16, 200), (17, 300), (18, 500), (19, 500)]:
            self._make_transport("delivery", date(2026, 3, d), [(self._product, q, 0)])
        self._make_transport("return", date(2026, 4, 27), [(self._product, 600, 0)])
        blocks = rcs.calc_rental_payment_blocks_by_template(
            self.env, self._contract, date(2026, 4, 1), date(2026, 4, 30)
        )
        block = blocks[0]
        # Dư đầu kỳ gộp 1 dòng = 2000 - 600 đối ứng = 1400.
        self.assertEqual(len(block["normal_lines"]), 1)
        self.assertTrue(block["normal_lines"][0]["is_bob"])
        self.assertEqual(block["normal_lines"][0]["qty"], 1400)
        rc = block["return_calc"]
        # Đối ứng chỉ lấy đúng 600 từ dư đầu kỳ.
        bob_off = [o for o in rc["offset_deliveries"] if o.get("is_bob")]
        self.assertEqual(len(bob_off), 1)
        self.assertEqual(bob_off[0]["qty"], 600)
        self.assertEqual(sum(r["qty"] for r in rc["returns"]), 600)
        self.assertEqual(
            sum(a["qty"] for a in rc["penalty_rows"]) + sum(a["qty"] for a in rc["returned_rows"]),
            600,
        )
        self.assertEqual(block["present_total_qty"], 1400)

    def test_excess_shown_in_blocks_and_not_billed(self):
        # Giao 100, chuyển thừa 20 -> tính tiền 80, hiển thị chuyển thừa đang giữ 20.
        self._make_transport("delivery", date(2026, 6, 10), [(self._product, 100, 20)])
        blocks = rcs.calc_rental_payment_blocks_by_template(
            self.env, self._contract, date(2026, 6, 1), date(2026, 6, 30)
        )
        block = blocks[0]
        self.assertEqual(block["excess_qty"], 20)
        self.assertEqual(block["present_total_qty"], 80)

    def test_fully_excess_block_shows_excess_only(self):
        # Giao 50 toàn bộ chuyển thừa -> không có dòng tính tiền nhưng vẫn hiện chuyển thừa.
        self._make_transport("delivery", date(2026, 6, 10), [(self._product, 50, 50)])
        blocks = rcs.calc_rental_payment_blocks_by_template(
            self.env, self._contract, date(2026, 6, 1), date(2026, 6, 30)
        )
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]["excess_qty"], 50)
        self.assertEqual(blocks[0]["present_total_qty"], 0)
        self.assertFalse(blocks[0]["normal_lines"])

    def test_return_deducts_excess_first_no_penalty(self):
        # Giao 120 (chuyển thừa 20) -> tính tiền 100. Trả 30: trừ 20 chuyển thừa trước
        # (không phạt), còn 10 mới vào logic phạt.
        self._make_transport("delivery", date(2026, 6, 10), [(self._product, 120, 20)])
        self._make_transport("return", date(2026, 6, 20), [(self._product, 30, 0)])
        blocks = rcs.calc_rental_payment_blocks_by_template(
            self.env, self._contract, date(2026, 6, 1), date(2026, 6, 30)
        )
        block = blocks[0]
        self.assertEqual(block["excess_qty"], 0)        # 20 chuyển thừa đã trả hết
        self.assertEqual(block["present_total_qty"], 90)  # 100 - 10 vào logic phạt
        rc = block["return_calc"]
        self.assertEqual(sum(a["qty"] for a in rc["penalty_rows"]), 10)
        # Dòng trả ĐỎ hiển thị ĐỦ số vật lý = 30 (10 tính tiền + 20 chuyển thừa).
        self.assertEqual(sum(r["qty"] for r in rc["returns"]), 30)
        # Phần chuyển thừa trả lại được tách riêng làm nguồn đối ứng.
        self.assertEqual(rc["excess_return_qty"], 20)

    def test_return_fully_excess_shows_physical_and_excess_return(self):
        # Giao 120 (chuyển thừa 20). Trả đúng 20 -> toàn bộ là chuyển thừa, không phạt.
        # Dòng trả phải hiện đủ 20 (vật lý) và excess_return_qty = 20.
        self._make_transport("delivery", date(2026, 6, 10), [(self._product, 120, 20)])
        self._make_transport("return", date(2026, 6, 20), [(self._product, 20, 0)])
        blocks = rcs.calc_rental_payment_blocks_by_template(
            self.env, self._contract, date(2026, 6, 1), date(2026, 6, 30)
        )
        block = blocks[0]
        self.assertEqual(block["excess_qty"], 0)
        self.assertEqual(block["present_total_qty"], 100)
        rc = block["return_calc"]
        self.assertIsNotNone(rc)
        self.assertEqual(rc["excess_return_qty"], 20)
        self.assertEqual(sum(r["qty"] for r in rc["returns"]), 20)
        self.assertEqual(sum(a["qty"] for a in rc["penalty_rows"]), 0)

    def test_penalty_row_carries_text_fields(self):
        # Dòng đối ứng trả mang đủ field cho text: ngày giao, ngày trả, số tháng phạt.
        self._make_transport("delivery", date(2026, 6, 10), [(self._product, 100, 0)])
        self._make_transport("return", date(2026, 6, 20), [(self._product, 30, 0)])
        blocks = rcs.calc_rental_payment_blocks_by_template(
            self.env, self._contract, date(2026, 6, 1), date(2026, 6, 30)
        )
        rc = blocks[0]["return_calc"]
        self.assertEqual(len(rc["penalty_rows"]), 1)
        agg = rc["penalty_rows"][0]
        self.assertEqual(agg["deliver_date"], date(2026, 6, 10))
        self.assertEqual(agg["return_date"], date(2026, 6, 20))
        self.assertEqual(agg["min_months"], 2)

    def test_payment_blocks_no_return_has_no_return_calc(self):
        # Không trả trong kỳ -> chỉ có đơn thuê bình thường, không có khối tính trả tối thiểu.
        self._make_transport("delivery", date(2026, 6, 10), [(self._product, 100, 0)])
        blocks = rcs.calc_rental_payment_blocks_by_template(
            self.env, self._contract, date(2026, 6, 1), date(2026, 6, 30)
        )
        self.assertEqual(len(blocks), 1)
        self.assertIsNone(blocks[0]["return_calc"])
        self.assertEqual(blocks[0]["present_total_qty"], 100)

    def test_upfront_return_after_minimum_is_not_penalty(self):
        # Delivered Jun 1, returned Sep 5 (after the 2-month minimum) -> normal return, no penalty.
        self._make_transport("delivery", date(2026, 6, 1), [(self._product, 100, 0)])
        self._make_transport("return", date(2026, 9, 5), [(self._product, 30, 0)])
        sep = list(
            rcs._build_map_product_and_date_to_line(
                self.env, self._contract, date(2026, 9, 1), date(2026, 9, 30)
            ).values()
        )
        self.assertFalse([l for l in sep if l["kind"] == "minimum"])
        returned = [l for l in sep if l["kind"] == "returned"]
        self.assertEqual(sum(l["qty"] for l in returned), 30)
        # billed only up to the actual return date (no minimum extension)
        self.assertTrue(all(l["end_date"] == date(2026, 9, 5) for l in returned))

    # ----- Scenario 5: multi-variant linear-meter pooled return matching -----
    def _make_multivariant_meter_contract(self):
        """Mẫu mét dài 2 biến thể (hệ số 1 và 2), HĐ kỳ tối thiểu 2 tháng."""
        md_categ = self.env["uom.category"].create({"name": "MD pool test"})
        uom_md = self.env["uom.uom"].create({
            "name": "Mét dài (pool test)",
            "category_id": md_categ.id,
            "uom_type": "reference",
            "is_linear_meter_variant": True,
        })
        attr = self.env["product.attribute"].create(
            {"name": "Length (pool test)", "create_variant": "always"}
        )
        val_1 = self.env["product.attribute.value"].create(
            {"name": "1m", "attribute_id": attr.id, "default_price_multiplier": 1.0}
        )
        val_2 = self.env["product.attribute.value"].create(
            {"name": "2m", "attribute_id": attr.id, "default_price_multiplier": 2.0}
        )
        tmpl = self.env["product.template"].create({
            "name": "Hộp pool test",
            "type": "product",
            "list_price": 1000.0,
            "uom_id": uom_md.id,
            "uom_po_id": uom_md.id,
            "attribute_line_ids": [
                (0, 0, {"attribute_id": attr.id, "value_ids": [(6, 0, [val_1.id, val_2.id])]})
            ],
        })
        by_mult = {
            v.product_template_attribute_value_ids.price_multiplier: v
            for v in tmpl.product_variant_ids
        }
        v1 = by_mult[1.0]
        v2 = by_mult[2.0]
        contract = self.env["rental.contract"].create({
            "a_company_party": self._a_company.id,
            "a_party": self._a_party.id,
            "b_company_party": self.env.company.partner_id.id,
            "b_party": self._b_party.id,
            "rental_billing_mode": "month",
            "minimum_rental_months": 2,
        })
        return contract, tmpl, v1, v2

    def _make_transport_for(self, contract, ttype, when, lines):
        return self.env["rr.transport"].create({
            "rental_contract_id": contract.id,
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

    def test_pooled_return_attributes_to_latest_lot_across_variants(self):
        # Như RC00083: lô mới nhất (10/07) gồm nhiều biến thể; biến thể V2 trả vượt phần
        # V2 của lô mới nhất. Khớp theo biến thể sẽ đẩy phần dư về lô cũ (không phạt),
        # còn khớp gộp mét dài dồn toàn bộ về lô mới nhất (phạt đủ kỳ tối thiểu).
        contract, tmpl, v1, v2 = self._make_multivariant_meter_contract()
        # Lô cũ 01/04 (đã quá 2 tháng tại 08): V2 = 100 cây.
        self._make_transport_for(contract, "delivery", date(2026, 4, 1), [(v2, 100, 0)])
        # Lô mới 10/07: V2 = 20 cây + V1 = 200 cây (tổng 40 + 200 = 240 mét).
        self._make_transport_for(contract, "delivery", date(2026, 7, 10), [(v2, 20, 0), (v1, 200, 0)])
        # Trả 100 cây V2 (= 200 mét) ngày 05/08.
        self._make_transport_for(contract, "return", date(2026, 8, 5), [(v2, 100, 0)])

        blocks = rcs.calc_rental_payment_blocks_by_template(
            self.env, contract, date(2026, 8, 1), date(2026, 8, 31)
        )
        block = next(b for b in blocks if b["tmpl_id"] == tmpl.id)
        rc = block["return_calc"]
        self.assertIsNotNone(rc)
        penalty = sum(a["qty"] for a in rc["penalty_rows"])
        returned = sum(a["qty"] for a in rc["returned_rows"])
        # Gộp mét dài: toàn bộ 200 mét trả dồn về lô 10/07 -> phạt hết, không có phần trả thường.
        self.assertEqual(penalty, 200)
        self.assertEqual(returned, 0)
        # Phần phạt gắn đúng lô giao 10/07.
        self.assertEqual({a["deliver_date"] for a in rc["penalty_rows"]}, {date(2026, 7, 10)})

    def test_pooled_return_spills_to_older_lot_when_latest_exhausted(self):
        # Trả vượt cả lô mới nhất -> phần dư mới rơi về lô cũ (không phạt).
        contract, tmpl, v1, v2 = self._make_multivariant_meter_contract()
        self._make_transport_for(contract, "delivery", date(2026, 4, 1), [(v2, 100, 0)])  # 200 mét cũ
        self._make_transport_for(contract, "delivery", date(2026, 7, 10), [(v1, 60, 0)])   # 60 mét mới
        # Trả 100 cây V2 = 200 mét ngày 05/08; lô mới chỉ có 60 mét.
        self._make_transport_for(contract, "return", date(2026, 8, 5), [(v2, 100, 0)])
        blocks = rcs.calc_rental_payment_blocks_by_template(
            self.env, contract, date(2026, 8, 1), date(2026, 8, 31)
        )
        block = next(b for b in blocks if b["tmpl_id"] == tmpl.id)
        rc = block["return_calc"]
        penalty = sum(a["qty"] for a in rc["penalty_rows"])
        returned = sum(a["qty"] for a in rc["returned_rows"])
        # 60 mét (lô 10/07) bị phạt + 140 mét (lô 01/04, quá kỳ) trả thường.
        self.assertEqual(penalty, 60)
        self.assertEqual(returned, 140)

    def test_spread_mode_still_distributes_over_months(self):
        self._contract.minimum_rental_billing_mode = "spread"
        self._make_transport("delivery", date(2026, 6, 10), [(self._product, 80, 0)])
        self._make_transport("return", date(2026, 6, 20), [(self._product, 30, 0)])
        # Return pushed to Aug 10: present 80 in June and July, net 50 only from August.
        jun = rcs._build_map_product_and_date_to_line(
            self.env, self._contract, date(2026, 6, 1), date(2026, 6, 30)
        )
        self.assertEqual(sum(l["qty"] for l in jun.values()), 80)
        jul = rcs._build_map_product_and_date_to_line(
            self.env, self._contract, date(2026, 7, 1), date(2026, 7, 31)
        )
        self.assertEqual(sum(l["qty"] for l in jul.values()), 80)
        aug = rcs._build_map_product_and_date_to_line(
            self.env, self._contract, date(2026, 8, 1), date(2026, 8, 31)
        )
        self.assertEqual(sum(l["qty"] for l in aug.values()), 50)
