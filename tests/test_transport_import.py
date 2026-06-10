# -*- coding: utf-8 -*-
import base64
from datetime import date
from io import BytesIO

from openpyxl import Workbook

from odoo.addons.rental.helper.import_transport_matrix import (
    build_import_template_bytes,
    parse_transport_matrix_xlsx,
)
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestTransportImport(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        company = cls.env.company
        cls._a_company = cls.env["res.partner"].create({
            "name": "Import Test Renter",
            "is_company": True,
            "customer_type": "renter",
        })
        cls._a_party = cls.env["res.partner"].create({
            "name": "Import A rep",
            "parent_id": cls._a_company.id,
        })
        cls._b_party = cls.env["res.partner"].create({
            "name": "Import B rep",
            "parent_id": company.partner_id.id,
        })
        cls._driver = cls.env["res.partner"].create({
            "name": "Import Driver",
            "customer_type": "driver",
        })
        cls._truck = cls.env["transport.truck"].create({
            "plate": "29H-80228",
            "name": "29H-80228",
            "company_id": company.id,
        })
        cls._product = cls.env["product.product"].create({
            "name": "Khóa giáo",
            "type": "product",
        })
        cls._contract = cls.env["rental.contract"].create({
            "a_company_party": cls._a_company.id,
            "a_party": cls._a_party.id,
            "b_company_party": company.partner_id.id,
            "b_party": cls._b_party.id,
        })
        cls.env["rental.contract.line"].create({
            "rental_contract_id": cls._contract.id,
            "product_tmpl_id": cls._product.product_tmpl_id.id,
            "price_unit": 100.0,
        })

    def _build_workbook_bytes(self, rows, product_header="Khóa giáo"):
        wb = Workbook()
        ws = wb.active
        ws.cell(14, 4).value = "Chủng loại/ Khối lượng"
        ws.cell(15, 4).value = product_header
        ws.cell(16, 4).value = product_header
        ws.merge_cells(start_row=15, start_column=4, end_row=16, end_column=4)
        start_row = 17
        for idx, row in enumerate(rows):
            r = start_row + idx
            ws.cell(r, 1).value = idx + 1
            ws.cell(r, 2).value = row["date"]
            ws.cell(r, 3).value = row["plate"]
            ws.cell(r, 4).value = row.get("qty")
        buf = BytesIO()
        wb.save(buf)
        return buf.getvalue()

    def test_parse_delivery_row(self):
        data = self._build_workbook_bytes([{
            "date": date(2026, 3, 22),
            "plate": "29H-80228",
            "qty": 600,
        }])
        parsed = parse_transport_matrix_xlsx(data, self.env, contract=self._contract)
        self.assertEqual(len(parsed["rows"]), 1)
        row = parsed["rows"][0]
        self.assertEqual(row["transport_type"], "delivery")
        self.assertEqual(row["lines"], [(self._product.id, 600)])
        self.assertFalse(row["errors"])

    def test_parse_return_row_with_negative_qty(self):
        data = self._build_workbook_bytes([{
            "date": date(2026, 3, 23),
            "plate": "29H-80228",
            "qty": -100,
        }])
        parsed = parse_transport_matrix_xlsx(data, self.env, contract=self._contract)
        row = parsed["rows"][0]
        self.assertEqual(row["transport_type"], "return")
        self.assertEqual(row["lines"], [(self._product.id, 100)])

    def test_product_mismatch_shows_detailed_error(self):
        data = self._build_workbook_bytes(
            [{
                "date": date(2026, 3, 22),
                "plate": "29H-80228",
                "qty": 10,
            }],
            product_header="SP Không Tồn Tại",
        )
        parsed = parse_transport_matrix_xlsx(data, self.env, contract=self._contract)
        self.assertTrue(parsed["product_mapping_errors"])
        detail = parsed["product_mapping_errors"][0]["detail"]
        self.assertIn("SP Không Tồn Tại", detail)
        self.assertIn("Khóa giáo", detail)

    def test_duplicate_in_file_is_error(self):
        row = {
            "date": date(2026, 3, 22),
            "plate": "29H-80228",
            "qty": 10,
        }
        data = self._build_workbook_bytes([row, row])
        parsed = parse_transport_matrix_xlsx(data, self.env, contract=self._contract)
        self.assertTrue(any("trùng ngày" in err for err in parsed["errors"]))

    def test_import_allows_existing_duplicate_on_contract(self):
        self.env["rr.transport"].create({
            "rental_contract_id": self._contract.id,
            "type": "delivery",
            "start_rental_or_return_date": date(2026, 3, 22),
            "driver_id": self._driver.id,
            "transport_truck_id": self._truck.id,
            "vehicle_start_time": date(2026, 3, 22),
            "transport_line_ids": [(0, 0, {
                "product_id": self._product.id,
                "qty": 5,
            })],
        })
        data = self._build_workbook_bytes([{
            "date": date(2026, 3, 22),
            "plate": "29H-80228",
            "qty": 20,
        }])
        wizard = self.env["rental.transport.import.wizard"].create({
            "rental_contract_id": self._contract.id,
            "default_driver_id": self._driver.id,
            "validate_picking": False,
            "import_file": base64.b64encode(data),
            "import_filename": "test.xlsx",
        })
        wizard.action_import_transports()
        transports = self._contract.rr_transport_ids.filtered(
            lambda t: t.start_rental_or_return_date == date(2026, 3, 22)
        )
        self.assertEqual(len(transports), 2)

    def test_import_creates_transport(self):
        data = self._build_workbook_bytes([{
            "date": date(2026, 4, 1),
            "plate": "30A-11111",
            "qty": 50,
        }])
        wizard = self.env["rental.transport.import.wizard"].create({
            "rental_contract_id": self._contract.id,
            "default_driver_id": self._driver.id,
            "auto_create_truck": True,
            "validate_picking": False,
            "import_file": base64.b64encode(data),
            "import_filename": "test.xlsx",
        })
        wizard.action_import_transports()
        transport = self._contract.rr_transport_ids.filtered(
            lambda t: t.start_rental_or_return_date == date(2026, 4, 1)
        )
        self.assertEqual(len(transport), 1)
        self.assertEqual(transport.type, "delivery")
        self.assertEqual(transport.transport_line_ids.qty, 50)

    def test_build_import_template_bytes(self):
        data = build_import_template_bytes(self._contract, self.env)
        self.assertTrue(data)
        parsed = parse_transport_matrix_xlsx(data, self.env, contract=self._contract)
        self.assertFalse(parsed["errors"])

    def test_import_validate_picking_allows_negative_stock(self):
        if not self.env["stock.warehouse"].search([("company_id", "=", self.env.company.id)], limit=1):
            self.env["stock.warehouse"].create({
                "name": "Import WH",
                "code": "IMP",
                "company_id": self.env.company.id,
            })
        data = self._build_workbook_bytes([{
            "date": date(2026, 5, 10),
            "plate": "99X-99999",
            "qty": 25,
        }])
        wizard = self.env["rental.transport.import.wizard"].create({
            "rental_contract_id": self._contract.id,
            "default_driver_id": self._driver.id,
            "auto_create_truck": True,
            "validate_picking": True,
            "import_file": base64.b64encode(data),
            "import_filename": "test.xlsx",
        })
        wizard.action_import_transports()
        transport = self._contract.rr_transport_ids.filtered(
            lambda t: t.start_rental_or_return_date == date(2026, 5, 10)
        )
        self.assertEqual(len(transport), 1)
        self.assertEqual(transport.state, "done")
        picking = transport.picking_ids.filtered(lambda p: p.state == "done" and not p.return_id)
        self.assertTrue(picking)
