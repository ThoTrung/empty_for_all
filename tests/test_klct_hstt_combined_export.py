# -*- coding: utf-8 -*-
from datetime import date
from io import BytesIO

from openpyxl import load_workbook

from odoo.addons.rental.services import rental_contract_services as rcs
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

    def _create_transport(self, when, qty):
        return self.env["rr.transport"].create({
            "rental_contract_id": self._contract.id,
            "type": "delivery",
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
