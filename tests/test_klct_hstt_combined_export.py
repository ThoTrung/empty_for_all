# -*- coding: utf-8 -*-
from datetime import date
from io import BytesIO
import base64

from openpyxl import Workbook, load_workbook

from odoo.addons.rental.services import rental_contract_services as rcs
from odoo.addons.rental.helper.xlsx_template_utils import find_transport_matrix_layout
from odoo.tests.common import TransactionCase


class TestKlctHsttCombinedExport(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        company = cls.env.company
        cls._a_company = cls.env["res.partner"].create({
            "name": "KLCT HSTT Renter",
            "is_company": True,
            "customer_type": "renter",
        })
        cls._a_party = cls.env["res.partner"].create({
            "name": "KLCT HSTT A rep",
            "parent_id": cls._a_company.id,
        })
        cls._b_party = cls.env["res.partner"].create({
            "name": "KLCT HSTT B rep",
            "parent_id": company.partner_id.id,
        })
        cls._driver = cls.env["res.partner"].create({
            "name": "KLCT HSTT Driver",
            "customer_type": "driver",
        })
        cls._truck = cls.env["transport.truck"].create({
            "plate": "29H-91001",
            "name": "29H-91001",
            "company_id": company.id,
        })
        cls._product = cls.env["product.product"].create({
            "name": "Khóa giáo KLCT-HSTT",
            "type": "product",
            "list_price": 100.0,
        })
        # Ensure income account so invoice creation works in tests.
        income = cls.env["account.account"].search([
            ("company_id", "=", company.id),
            ("account_type", "=", "income"),
        ], limit=1)
        if not income:
            income = cls.env["account.account"].create({
                "name": "KLCT HSTT Income",
                "code": "KLCTHSTTINC",
                "account_type": "income",
                "company_id": company.id,
            })
        cls._product.property_account_income_id = income.id
        cls._product.product_tmpl_id.property_account_income_id = income.id

        cls._contract = cls.env["rental.contract"].create({
            "a_company_party": cls._a_company.id,
            "a_party": cls._a_party.id,
            "b_company_party": company.partner_id.id,
            "b_party": cls._b_party.id,
            "rental_billing_mode": "day",
            "include_start_day_current": False,
            "include_start_day_bob": True,
        })
        cls.env["rental.contract.line"].create({
            "contract_id": cls._contract.id,
            "product_tmpl_id": cls._product.product_tmpl_id.id,
            "price_unit": 100.0,
        })
        # Avoid DB-uploaded HSTT layouts (may merge row 13); use module static + start_row 13.
        cls.env["rental.template"].with_context(active_test=False).search([
            ("template_type", "=", "rental_invoice_xlsx"),
        ]).write({"active": False, "is_default": False})

    def _create_transport(self, when, qty, transport_type="delivery"):
        return self.env["rr.transport"].create({
            "rental_contract_id": self._contract.id,
            "type": transport_type,
            "state": "done",
            "start_rental_or_return_date": when,
            "driver_id": self._driver.id,
            "transport_truck_id": self._truck.id,
            "vehicle_start_time": when,
            "plate": "29H-91001",
            "transport_line_ids": [(0, 0, {
                "product_id": self._product.id,
                "qty": qty,
            })],
        })

    def test_combined_workbook_has_two_named_sheets_with_formulas(self):
        start_date = date(2026, 4, 1)
        end_date = date(2026, 4, 30)
        self._create_transport(date(2026, 4, 10), 50)

        buffer, _subtotal = self._contract._build_klct_hstt_xlsx_buffer(start_date, end_date)
        wb = load_workbook(BytesIO(buffer.getvalue()))
        self.assertEqual(wb.sheetnames[0], "KLCT 04-2026")
        self.assertEqual(wb.sheetnames[1], "HSTT 04-2026")

        hstt = wb["HSTT 04-2026"]
        # Data starts at row 13; first billing line should use Excel formulas.
        qty_cell = hstt.cell(13, 6).value
        days_cell = hstt.cell(13, 7).value
        amount_cell = hstt.cell(13, 9).value
        self.assertIsInstance(qty_cell, str)
        self.assertTrue(str(qty_cell).startswith("="))
        self.assertIn("KLCT 04-2026", str(qty_cell))
        self.assertEqual(days_cell, "=C13-B13")
        self.assertEqual(amount_cell, "=F13*G13*H13")

        # Dates must be real date values for C-B formulas.
        self.assertEqual(hstt.cell(13, 2).value.date(), date(2026, 4, 10))
        self.assertEqual(hstt.cell(13, 3).value.date(), date(2026, 4, 30))

    def test_orphan_return_is_negative_in_klct_and_hstt_reference(self):
        start_date = date(2026, 4, 1)
        end_date = date(2026, 4, 30)
        self._create_transport(date(2026, 4, 10), 12, transport_type="return")
        self._create_transport(date(2026, 4, 11), 20, transport_type="delivery")

        buffer, _subtotal = self._contract._build_klct_hstt_xlsx_buffer(
            start_date, end_date
        )
        wb = load_workbook(BytesIO(buffer.getvalue()))
        klct = wb["KLCT 04-2026"]
        _title, _h2, _h3, start_row = find_transport_matrix_layout(klct)
        self.assertEqual(klct.cell(start_row, 4).value, -12)
        self.assertEqual(klct.cell(start_row + 1, 4).value, 20)
        self.assertEqual(klct.cell(start_row + 2, 4).value, 8)

        hstt = wb["HSTT 04-2026"]
        self.assertEqual(
            hstt.cell(13, 6).value,
            f"='KLCT 04-2026'!D{start_row}",
        )
        self.assertEqual(
            hstt.cell(14, 6).value,
            f"='KLCT 04-2026'!D{start_row + 1}",
        )

    def test_opening_qty_with_period_return_is_not_double_counted(self):
        self._contract.rental_billing_mode = "month"
        start_date = date(2026, 4, 1)
        end_date = date(2026, 4, 30)
        self._create_transport(date(2026, 3, 10), 100)
        self._create_transport(date(2026, 4, 10), 30, transport_type="return")

        buffer, _subtotal = self._contract._build_klct_hstt_xlsx_buffer(
            start_date, end_date
        )
        wb = load_workbook(BytesIO(buffer.getvalue()))
        klct = wb["KLCT 04-2026"]
        _title, _h2, _h3, start_row = find_transport_matrix_layout(klct)
        self.assertEqual(klct.cell(start_row, 4).value, 100)
        self.assertEqual(klct.cell(start_row + 1, 4).value, -30)
        self.assertEqual(klct.cell(start_row + 2, 4).value, 70)

        hstt = wb["HSTT 04-2026"]
        # The opening KLCT cell is 100, but only 70 remains rented through month end.
        # The returned 30 is charged separately through its return date.
        self.assertEqual(hstt.cell(13, 6).value, 70)
        self.assertEqual(hstt.cell(18, 6).value, 30)
        self.assertEqual(hstt.cell(18, 9).value, "=F18*G18*H18/30")

    def test_same_day_delivery_and_return_use_direction_specific_rows(self):
        start_date = date(2026, 4, 1)
        end_date = date(2026, 4, 30)
        # Return first makes it an orphan; the later delivery remains a normal lot.
        self._create_transport(date(2026, 4, 10), 5, transport_type="return")
        self._create_transport(date(2026, 4, 10), 9, transport_type="delivery")

        buffer, _subtotal = self._contract._build_klct_hstt_xlsx_buffer(
            start_date, end_date
        )
        wb = load_workbook(BytesIO(buffer.getvalue()))
        klct = wb["KLCT 04-2026"]
        _title, _h2, _h3, start_row = find_transport_matrix_layout(klct)
        self.assertEqual(klct.cell(start_row, 4).value, -5)
        self.assertEqual(klct.cell(start_row + 1, 4).value, 9)
        self.assertEqual(klct.cell(start_row + 2, 4).value, 4)

        hstt = wb["HSTT 04-2026"]
        self.assertEqual(
            hstt.cell(13, 6).value,
            (
                f"=SUM('KLCT 04-2026'!D{start_row},"
                f"'KLCT 04-2026'!D{start_row + 1})"
            ),
        )
        self.assertEqual(hstt.cell(14, 6).value, 4)

    def test_standalone_invoice_export_still_writes_literal_values(self):
        start_date = date(2026, 4, 1)
        end_date = date(2026, 4, 30)
        self._create_transport(date(2026, 4, 10), 50)

        buffer = self._contract._build_rental_payment_xlsx_buffer(start_date, end_date)
        wb = load_workbook(BytesIO(buffer.getvalue()))
        ws = wb.active
        self.assertEqual(ws.cell(13, 6).value, 50)
        self.assertIsInstance(ws.cell(13, 7).value, (int, float))
        self.assertIsInstance(ws.cell(13, 9).value, (int, float))
        self.assertIsInstance(ws.cell(13, 2).value, str)

    def test_include_start_day_current_adds_plus_one_in_formula(self):
        self._contract.include_start_day_current = True
        start_date = date(2026, 4, 1)
        end_date = date(2026, 4, 30)
        self._create_transport(date(2026, 4, 10), 20)

        buffer, _subtotal = self._contract._build_klct_hstt_xlsx_buffer(start_date, end_date)
        wb = load_workbook(BytesIO(buffer.getvalue()))
        hstt = wb["HSTT 04-2026"]
        self.assertEqual(hstt.cell(13, 7).value, "=C13-B13+1")

    def test_hstt_days_formula_subtracts_holidays(self):
        """Excel G must subtract holiday days so SUM(I) matches invoice Python total."""
        self._contract.include_start_day_bob = True
        self._contract.include_start_day_current = False
        # Opening stock before period → bob line [01/02 → 28/02] with include start.
        self._create_transport(date(2026, 1, 15), 10)
        self.env["rental.holiday"].create({
            "name": "Nghỉ Tết KLCT-HSTT",
            "date_from": date(2026, 2, 14),
            "date_to": date(2026, 2, 20),
            "company_id": self.env.company.id,
        })
        start_date = date(2026, 2, 1)
        end_date = date(2026, 2, 28)

        buffer, hstt_subtotal = self._contract._build_klct_hstt_xlsx_buffer(start_date, end_date)
        wb = load_workbook(BytesIO(buffer.getvalue()))
        hstt = wb["HSTT 02-2026"]
        # 7 holiday days on [B,C] with include_start → MAX(0,C-B+1-7)
        self.assertEqual(hstt.cell(13, 7).value, "=MAX(0,C13-B13+1-7)")

        bob_map, map_map = rcs.calc_rental_payment_table_grouped_by_template(
            self.env, self._contract, start_date, end_date
        )
        fee_lines = self._contract._rental_period_transport_fee_lines(start_date, end_date)
        expected = float(int(round(
            self._contract._payment_table_subtotal(bob_map, map_map, fee_lines)
        )))
        self.assertAlmostEqual(float(int(round(hstt_subtotal))), expected, places=2)

        # Invoice from export must match the same holiday-aware subtotal.
        self.env["rental.transport.matrix"].search([
            ("rental_contract_id", "=", self._contract.id),
        ]).unlink()
        action = self._contract.action_export_klct_hstt_excel(start_date, end_date)
        self.assertEqual(action["type"], "ir.actions.act_url")
        move = self.env["account.move"].search([
            ("rental_contract_id", "=", self._contract.id),
        ], limit=1)
        self.assertTrue(move)
        self.assertAlmostEqual(move.invoice_line_ids.price_unit, expected, places=2)

    def test_action_export_klct_hstt_excel_creates_matrix_and_one_line_invoice(self):
        start_date = date(2026, 4, 1)
        end_date = date(2026, 4, 30)
        self._create_transport(date(2026, 4, 10), 10)

        bob_map, map_map = rcs.calc_rental_payment_table_grouped_by_template(
            self.env, self._contract, start_date, end_date
        )
        fee_lines = self._contract._rental_period_transport_fee_lines(start_date, end_date)
        expected = float(int(round(
            self._contract._payment_table_subtotal(bob_map, map_map, fee_lines)
        )))

        action = self._contract.action_export_klct_hstt_excel(start_date, end_date)
        self.assertEqual(action["type"], "ir.actions.act_url")
        self.assertIn("/web/content/", action["url"])
        self.assertIn("download=1", action["url"])

        matrices = self.env["rental.transport.matrix"].search([
            ("rental_contract_id", "=", self._contract.id),
            ("start_date", "=", start_date),
            ("end_date", "=", end_date),
        ])
        self.assertEqual(len(matrices), 1)

        moves = self.env["account.move"].search([
            ("rental_contract_id", "=", self._contract.id),
        ])
        self.assertEqual(len(moves), 1)
        lines = moves.invoice_line_ids
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines.product_id.name, "Tổng thanh toán: 04-2026")
        self.assertIn("Tổng thanh toán: 04-2026", lines.name)
        self.assertEqual(lines.quantity, 1)
        self.assertAlmostEqual(lines.price_unit, expected, places=2)
        self.assertAlmostEqual(moves.amount_untaxed, expected, places=2)
        self.assertTrue(lines.tax_ids)
        self.assertAlmostEqual(lines.tax_ids[0].amount, 8.0, places=1)

    def test_hstt_total_product_replaces_stale_tax_with_eight_percent(self):
        tax_10 = self.env["account.tax"].search([
            ("company_id", "=", self.env.company.id),
            ("type_tax_use", "=", "sale"),
            ("amount", "=", 10.0),
            ("amount_type", "=", "percent"),
        ], limit=1)
        if not tax_10:
            tax_10 = self.env["account.tax"].create({
                "name": "10% HSTT stale test",
                "amount": 10.0,
                "amount_type": "percent",
                "type_tax_use": "sale",
                "company_id": self.env.company.id,
            })
        product = self._contract._get_or_create_hstt_total_product(date(2026, 4, 30))
        product.taxes_id = [(6, 0, tax_10.ids)]

        product = self._contract._get_or_create_hstt_total_product(date(2026, 4, 30))

        self.assertEqual(product.taxes_id.amount, 8.0)

    def test_action_export_klct_hstt_excel_overlap_returns_wizard(self):
        start_date = date(2026, 4, 1)
        end_date = date(2026, 4, 30)
        self._create_transport(date(2026, 4, 10), 10)
        self.env["rental.transport.matrix"].create({
            "rental_contract_id": self._contract.id,
            "start_date": start_date,
            "end_date": end_date,
            "name": "Existing matrix",
        })
        moves_before = self.env["account.move"].search_count([
            ("rental_contract_id", "=", self._contract.id),
        ])
        action = self._contract.action_export_klct_hstt_excel(start_date, end_date)
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "rental.transport.matrix.overlap.wizard")
        moves_after = self.env["account.move"].search_count([
            ("rental_contract_id", "=", self._contract.id),
        ])
        self.assertEqual(moves_before, moves_after)

    def _create_transport_with_fee(self, when, qty, fee):
        transport = self._create_transport(when, qty)
        transport.fee = fee
        return transport

    def test_unbilled_fee_filter_by_cutoff_and_marks_on_export(self):
        start_date = date(2026, 6, 1)
        end_date = date(2026, 6, 30)
        cutoff = date(2026, 6, 30)
        t1 = self._create_transport_with_fee(date(2026, 6, 2), 5, 1_000_000)
        t2 = self._create_transport_with_fee(date(2026, 6, 7), 5, 1_000_000)
        t3 = self._create_transport_with_fee(date(2026, 6, 29), 5, 1_000_000)
        # Future trip beyond cutoff — must not be billed yet.
        t_future = self._create_transport_with_fee(date(2026, 7, 5), 5, 500_000)

        fee_lines = self._contract._rental_unbilled_transport_fee_lines(cutoff)
        self.assertEqual(len(fee_lines), 3)
        self.assertAlmostEqual(sum(fl["amount"] for fl in fee_lines), 3_000_000)

        empty_lines = self._contract._rental_unbilled_transport_fee_lines(False)
        self.assertEqual(empty_lines, [])

        bob_map, map_map = rcs.calc_rental_payment_table_grouped_by_template(
            self.env, self._contract, start_date, end_date
        )
        expected = float(int(round(
            self._contract._payment_table_subtotal(bob_map, map_map, fee_lines)
        )))

        action = self._contract.action_export_klct_hstt_excel(
            start_date, end_date, transport_fee_until_date=cutoff
        )
        self.assertEqual(action["type"], "ir.actions.act_url")

        for t in (t1, t2, t3):
            self.assertEqual(t.fee_billed_date, cutoff)
            self.assertTrue(t.fee_invoice_id)
        self.assertFalse(t_future.fee_billed_date)
        self.assertFalse(t_future.fee_invoice_id)

        move = self.env["account.move"].search([
            ("rental_contract_id", "=", self._contract.id),
        ], limit=1)
        self.assertEqual(move.transport_fee_until_date, cutoff)
        self.assertAlmostEqual(move.invoice_line_ids.price_unit, expected, places=2)

        # Second period must not pick up already-billed fees.
        later_fees = self._contract._rental_unbilled_transport_fee_lines(date(2026, 7, 31))
        self.assertEqual(len(later_fees), 1)
        self.assertEqual(later_fees[0]["transport_id"], t_future.id)

    def test_hstt_fee_section_one_row_plus_detail_sheet(self):
        start_date = date(2026, 6, 1)
        end_date = date(2026, 6, 30)
        self._create_transport_with_fee(date(2026, 6, 2), 10, 1_000_000)
        self._create_transport_with_fee(date(2026, 6, 7), 10, 1_000_000)
        self._create_transport_with_fee(date(2026, 6, 29), 10, 1_000_000)

        buffer, subtotal = self._contract._build_klct_hstt_xlsx_buffer(
            start_date, end_date, transport_fee_until_date=end_date
        )
        wb = load_workbook(BytesIO(buffer.getvalue()))
        self.assertIn("Chi tiết phí VC", wb.sheetnames)
        detail = wb["Chi tiết phí VC"]
        self.assertEqual(detail.cell(1, 1).value, "Ngày")
        # 3 fee rows + header + total row
        self.assertEqual(detail.cell(2, 4).value, 1_000_000)
        self.assertEqual(detail.cell(4, 4).value, 1_000_000)
        self.assertEqual(detail.cell(5, 3).value, "Tổng")
        self.assertEqual(detail.cell(5, 4).value, 3_000_000)

        hstt = wb["HSTT 06-2026"]
        fee_header_row = None
        for r in range(13, 40):
            if hstt.cell(r, 4).value == "Phí vận chuyển":
                fee_header_row = r
                break
        self.assertIsNotNone(fee_header_row)
        summary_row = fee_header_row + 1
        self.assertEqual(hstt.cell(summary_row, 4).value, "Phí vận chuyển (3 chuyến)")
        self.assertEqual(hstt.cell(summary_row, 9).value, 3_000_000)
        # No per-transport fee rows after the summary.
        self.assertNotEqual(
            hstt.cell(summary_row + 1, 4).value or "",
            "Phí vận chuyển TR",
        )
        self.assertGreaterEqual(subtotal, 3_000_000)

    def test_regenerate_klct_hstt_keeps_invoice_fees(self):
        start_date = date(2026, 6, 1)
        end_date = date(2026, 6, 30)
        t1 = self._create_transport_with_fee(date(2026, 6, 2), 10, 800_000)
        self._contract.action_export_klct_hstt_excel(
            start_date, end_date, transport_fee_until_date=end_date
        )
        move = t1.fee_invoice_id
        self.assertTrue(move)

        buffer, subtotal = self._contract._build_klct_hstt_xlsx_buffer(
            start_date, end_date, fee_invoice=move
        )
        wb = load_workbook(BytesIO(buffer.getvalue()))
        self.assertIn("Chi tiết phí VC", wb.sheetnames)
        detail = wb["Chi tiết phí VC"]
        self.assertEqual(detail.cell(2, 4).value, 800_000)
        self.assertGreaterEqual(subtotal, 800_000)

        # Unbilled query must be empty for this trip after billing.
        self.assertEqual(
            self._contract._rental_unbilled_transport_fee_lines(end_date),
            [],
        )

    def _make_hstt_template_bytes_start_row_15(self):
        """Minimal HSTT workbook: confirmation merge on row 13, header 14, data from 15."""
        wb = Workbook()
        ws = wb.active
        ws.title = "GT thuê"
        ws["A13"] = (
            "Hai bên cùng nhau xác nhận khối lượng từ ngày {{start_date}} "
            "đến {{end_date}} với số liệu cụ thể như sau:"
        )
        ws.merge_cells("A13:I13")
        headers = [
            "STT",
            "Ngày thuê",
            "Đến ngày",
            "Nội dung",
            "ĐVT",
            "Số lượng",
            "Thời gian thuê (ngày)",
            "Đơn giá thuê/\n1 ngày (chưa VAT)",
            "Thành tiền",
        ]
        for col, header in enumerate(headers, start=1):
            ws.cell(14, col).value = header
        for r in range(15, 215):
            ws.cell(r, 1).value = r - 14
        ws.cell(215, 5).value = "Cộng tiền thuê trước thuế"
        ws.cell(215, 9).value = "=SUM(I15:I214)"
        ws.cell(216, 5).value = "Thuế GTGT 8%"
        ws.cell(217, 5).value = "Tổng Cộng tiền thuê sau thuế"
        ws.cell(218, 1).value = "(Bằng chữ: {{total_after_tax_string}}./.)"
        buf = BytesIO()
        wb.save(buf)
        return buf.getvalue()

    def test_data_start_row_15_writes_below_merged_confirmation(self):
        """Uploaded template with data_start_row=15 must not write into A13:I13 merge."""
        start_date = date(2026, 4, 1)
        end_date = date(2026, 4, 30)
        self._create_transport(date(2026, 4, 10), 50)

        self.env["rental.template"].with_context(active_test=False).search([
            ("template_type", "=", "rental_invoice_xlsx"),
        ]).write({"active": False, "is_default": False})
        self.env["rental.template"].create({
            "name": "HSTT start row 15",
            "company_id": self._contract.company_id.id,
            "template_type": "rental_invoice_xlsx",
            "data_start_row": 15,
            "is_default": True,
            "file_name": "hstt_row15.xlsx",
            "file_data": base64.b64encode(self._make_hstt_template_bytes_start_row_15()),
        })

        buffer, _subtotal = self._contract._build_klct_hstt_xlsx_buffer(start_date, end_date)
        wb = load_workbook(BytesIO(buffer.getvalue()))
        hstt = wb["HSTT 04-2026"]

        # Confirmation row kept (placeholders = period dates); not overwritten by billing.
        conf = hstt.cell(13, 1).value or ""
        self.assertIn("01/04/2026", conf)
        self.assertIn("30/04/2026", conf)
        # Non-anchor merged cells stay empty (read-only MergedCell).
        from openpyxl.cell.cell import MergedCell
        self.assertTrue(isinstance(hstt.cell(13, 2), MergedCell) or hstt.cell(13, 2).value in (None, ""))

        # First billing line starts at configured row 15 (delivery 10/04).
        self.assertEqual(hstt.cell(15, 2).value.date(), date(2026, 4, 10))
        self.assertEqual(hstt.cell(15, 3).value.date(), date(2026, 4, 30))
        self.assertEqual(hstt.cell(15, 7).value, "=C15-B15")
        self.assertEqual(hstt.cell(15, 9).value, "=F15*G15*H15")

    def test_hstt_placeholders_include_contract_number_and_date(self):
        """HSTT XLSX replaces {{contract_number}} / {{contract_date}} from contract."""
        self._contract.write({
            "contract_number": "125 /HĐKT/XDMT – TLP",
            "contract_date": "2026-07-05",
        })
        wb = Workbook()
        ws = wb.active
        ws["A1"] = "Số HĐ: {{contract_number}}"
        ws["A2"] = "Ngày HĐ: {{contract_date}}"
        self._contract._rental_invoice_xlsx_apply_placeholders(
            ws, date(2026, 4, 1), date(2026, 4, 30)
        )
        self.assertEqual(ws["A1"].value, "Số HĐ: 125 /HĐKT/XDMT – TLP")
        self.assertEqual(ws["A2"].value, "Ngày HĐ: ngày 05 tháng 07 năm 2026")
