# -*- coding: utf-8 -*-
from datetime import date

from odoo.tests.common import TransactionCase


class TestTransportFeeExport(TransactionCase):
    """List Excel export appends tổng giá vận chuyển."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        company = cls.env.company
        cls._a_company = cls.env["res.partner"].create({
            "name": "Fee Export Renter",
            "is_company": True,
            "customer_type": "company",
            "is_rental_customer": True,
            "company_id": company.id,
        })
        cls._a_party = cls.env["res.partner"].create({
            "name": "Fee Export A rep",
            "parent_id": cls._a_company.id,
            "company_id": company.id,
        })
        cls._b_party = cls.env["res.partner"].create({
            "name": "Fee Export B rep",
            "parent_id": company.partner_id.id,
            "company_id": company.id,
        })
        cls._driver = cls.env["res.partner"].create({
            "name": "Fee Export Driver",
            "customer_type": "driver",
            "company_id": company.id,
        })
        cls._truck = cls.env["transport.truck"].create({
            "plate": "29H-93001",
            "name": "29H-93001",
            "company_id": company.id,
        })
        cls._product = cls.env["product.product"].create({
            "name": "Khóa giáo fee-export",
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

    def _make_transport(self, fee):
        when = date(2026, 6, 10)
        return self.env["rr.transport"].create({
            "rental_contract_id": self._contract.id,
            "type": "delivery",
            "state": "draft",
            "start_rental_or_return_date": when,
            "driver_id": self._driver.id,
            "transport_truck_id": self._truck.id,
            "vehicle_start_time": when,
            "plate": "29H-93001",
            "fee": fee,
            "transport_line_ids": [(0, 0, {
                "product_id": self._product.id,
                "qty": 1,
            })],
        })

    def test_export_data_appends_fee_total_row(self):
        t1 = self._make_transport(100_000)
        t2 = self._make_transport(50_000)
        transports = t1 | t2
        result = transports.export_data(["code", "fee"])
        datas = result["datas"]
        self.assertEqual(len(datas), 3)
        self.assertEqual(datas[-1][0], "Tổng giá vận chuyển")
        self.assertEqual(datas[-1][1], "=SUM(B2:B3)")

    def test_excel_col_letter(self):
        letter = self.env["rr.transport"]._excel_col_letter
        self.assertEqual(letter(0), "A")
        self.assertEqual(letter(1), "B")
        self.assertEqual(letter(25), "Z")
        self.assertEqual(letter(26), "AA")
