# -*- coding: utf-8 -*-
from datetime import date
from io import BytesIO

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

from odoo.addons.rental.helper.transport_matrix_export import build_transport_matrix_xlsx_bytes
from odoo.addons.rental.helper.xlsx_template_utils import (
    find_transport_matrix_footer_row,
    find_transport_matrix_layout,
)
from odoo.tests.common import TransactionCase


class TestTransportMatrixXlsxExport(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        company = cls.env.company
        cls._a_company = cls.env["res.partner"].create({
            "name": "Matrix Export Renter",
            "is_company": True,
            "customer_type": "renter",
        })
        cls._a_party = cls.env["res.partner"].create({
            "name": "Matrix Export A rep",
            "parent_id": cls._a_company.id,
        })
        cls._b_party = cls.env["res.partner"].create({
            "name": "Matrix Export B rep",
            "parent_id": company.partner_id.id,
        })
        cls._driver = cls.env["res.partner"].create({
            "name": "Matrix Export Driver",
            "customer_type": "driver",
        })
        cls._truck = cls.env["transport.truck"].create({
            "plate": "29H-90001",
            "name": "29H-90001",
            "company_id": company.id,
        })
        cls._product = cls.env["product.product"].create({
            "name": "Khóa giáo export",
            "type": "product",
        })
        cls._contract = cls.env["rental.contract"].create({
            "a_company_party": cls._a_company.id,
            "a_party": cls._a_party.id,
            "b_company_party": company.partner_id.id,
            "b_party": cls._b_party.id,
        })
        cls.env["rental.contract.line"].create({
            "contract_id": cls._contract.id,
            "product_tmpl_id": cls._product.product_tmpl_id.id,
            "price_unit": 100.0,
        })

    def _create_transport(self, when, qty, plate="29H-90001"):
        return self.env["rr.transport"].create({
            "rental_contract_id": self._contract.id,
            "type": "delivery",
            "start_rental_or_return_date": when,
            "driver_id": self._driver.id,
            "transport_truck_id": self._truck.id,
            "vehicle_start_time": when,
            "plate": plate,
            "transport_line_ids": [(0, 0, {
                "product_id": self._product.id,
                "qty": qty,
            })],
        })

    def _export_workbook(self, start_date, end_date):
        data = build_transport_matrix_xlsx_bytes(
            self.env, self._contract, start_date, end_date,
        )
        return load_workbook(BytesIO(data)), data

    def test_period_placeholders_are_replaced(self):
        start_date = date(2026, 6, 1)
        end_date = date(2026, 6, 30)
        self._create_transport(date(2026, 6, 2), 10)
        wb, _data = self._export_workbook(start_date, end_date)
        ws = wb.active
        period_text = ws.cell(6, 1).value or ""
        self.assertIn("01/06/2026", period_text)
        self.assertIn("30/06/2026", period_text)
        self.assertNotIn("{{from_date}}", period_text)
        self.assertNotIn("{{to_date}}", period_text)

    def test_footer_rows_remain_visible_and_compact(self):
        start_date = date(2026, 6, 1)
        end_date = date(2026, 6, 30)
        self._create_transport(date(2026, 6, 2), 10)
        self._create_transport(date(2026, 6, 7), 20)
        wb, _data = self._export_workbook(start_date, end_date)
        ws = wb.active

        footer_row = find_transport_matrix_footer_row(ws, min_row=17)
        self.assertTrue(footer_row, "Footer row should be detected")
        self.assertFalse(getattr(ws.row_dimensions[footer_row], "hidden", False))
        self.assertFalse(getattr(ws.row_dimensions[footer_row + 1], "hidden", False))

        footer_values = []
        for row in (footer_row, footer_row + 1):
            for cell in ws[row]:
                if isinstance(cell.value, str):
                    footer_values.append(cell.value)
        joined = " ".join(footer_values)
        self.assertIn("Hà Nội", joined)
        self.assertIn("Đơn vị", joined)

        # Footer sits immediately below data (2 transports + total = 3 rows).
        _title, _h2, _h3, start_row = find_transport_matrix_layout(ws)
        self.assertEqual(footer_row, start_row + 3)

    def test_product_columns_keep_fixed_width(self):
        start_date = date(2026, 6, 1)
        end_date = date(2026, 6, 30)
        self._create_transport(date(2026, 6, 2), 2000)
        wb, _data = self._export_workbook(start_date, end_date)
        ws = wb.active
        dim = ws.column_dimensions[get_column_letter(4)]
        self.assertTrue(dim.width)
        self.assertFalse(dim.bestFit)
