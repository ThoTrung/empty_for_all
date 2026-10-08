# -*- coding: utf-8 -*-
from datetime import date

from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from lxml import etree


@tagged("post_install", "-at_install", "subrent_contract_moves")
class TestSubrentContractEmbedMoves(TransactionCase):
    """Phase 2 — receipt/return O2M on contract; confirm still updates qty_open."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.supplier = cls.env["res.partner"].create({
            "name": "NCC Embed Moves",
            "is_company": True,
            "customer_type": "company",
            "is_rental_supplier": True,
            "company_id": cls.company.id,
        })
        cls.product = cls.env["product.product"].create({
            "name": "SP Embed Moves",
            "type": "product",
            "list_price": 1000.0,
        })
        cls.contract = cls.env["rental.subrent.contract"].create({
            "supplier_id": cls.supplier.id,
            "policy_code": "simple",
            "date_start": date(2026, 5, 1),
            "company_id": cls.company.id,
            "line_ids": [(0, 0, {
                "product_tmpl_id": cls.product.product_tmpl_id.id,
                "cost_unit": 2000.0,
            })],
        })
        cls.contract.action_activate()

    def test_form_arch_has_moves_tab(self):
        arch, _view = self.env["rental.subrent.contract"]._get_view(view_type="form")
        xml = etree.tostring(arch, encoding="unicode")
        self.assertIn('name="subrent_moves"', xml)
        self.assertIn("receipt_ids", xml)
        self.assertIn("return_ids", xml)

    def test_create_receipt_return_via_o2m_confirm(self):
        receipt = self.env["rental.subrent.receipt"].with_context(
            default_subrent_contract_id=self.contract.id,
            default_company_id=self.company.id,
        ).create({
            "subrent_contract_id": self.contract.id,
            "date": date(2026, 5, 1),
            "stock_flow": "into_stock",
            "company_id": self.company.id,
            "line_ids": [(0, 0, {"product_id": self.product.id, "qty": 10})],
        })
        self.assertIn(receipt, self.contract.receipt_ids)
        receipt.action_confirm()
        line = self.contract.line_ids[:1]
        self.assertEqual(line.qty_received, 10)
        self.assertEqual(line.qty_open, 10)

        ret = self.env["rental.subrent.return"].with_context(
            default_subrent_contract_id=self.contract.id,
            default_company_id=self.company.id,
        ).create({
            "subrent_contract_id": self.contract.id,
            "date": date(2026, 5, 15),
            "company_id": self.company.id,
            "line_ids": [(0, 0, {"product_id": self.product.id, "qty": 3})],
        })
        self.assertIn(ret, self.contract.return_ids)
        ret.action_confirm()
        line.invalidate_recordset()
        self.assertEqual(line.qty_returned, 3)
        self.assertEqual(line.qty_open, 7)
