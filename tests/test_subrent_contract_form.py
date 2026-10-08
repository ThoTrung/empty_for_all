# -*- coding: utf-8 -*-
from datetime import date

from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from lxml import etree


@tagged("post_install", "-at_install", "subrent_contract_form")
class TestSubrentContractFormEnrich(TransactionCase):
    """Phase 1 — meta + representatives on rental.subrent.contract."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.supplier = cls.env["res.partner"].create({
            "name": "NCC Form Enrich",
            "is_company": True,
            "customer_type": "company",
            "is_rental_supplier": True,
            "company_id": cls.company.id,
        })
        cls.supplier_rep = cls.env["res.partner"].create({
            "name": "Đại diện NCC",
            "type": "contact",
            "parent_id": cls.supplier.id,
            "customer_type": "other",
            "company_id": cls.company.id,
        })
        cls.our_rep = cls.env["res.partner"].create({
            "name": "Đại diện ta",
            "type": "contact",
            "parent_id": cls.company.partner_id.id,
            "customer_type": "other",
            "company_id": cls.company.id,
        })
        cls.product = cls.env["product.product"].create({
            "name": "SP Form Enrich",
            "type": "product",
            "list_price": 1000.0,
        })

    def test_create_with_meta_and_reps(self):
        contract = self.env["rental.subrent.contract"].create({
            "supplier_id": self.supplier.id,
            "policy_code": "simple",
            "contract_date": date(2026, 3, 1),
            "contract_number": "01/HĐTN/NCC",
            "supplier_representative_id": self.supplier_rep.id,
            "our_representative_id": self.our_rep.id,
            "date_start": date(2026, 3, 1),
            "company_id": self.company.id,
            "line_ids": [(0, 0, {
                "product_tmpl_id": self.product.product_tmpl_id.id,
                "cost_unit": 1500.0,
            })],
        })
        self.assertEqual(contract.contract_number, "01/HĐTN/NCC")
        self.assertEqual(contract.supplier_representative_id, self.supplier_rep)
        self.assertEqual(contract.our_representative_id, self.our_rep)
        self.assertEqual(contract.company_partner_id, self.company.partner_id)
        # Existing simple HĐ still activates
        contract.action_activate()
        self.assertEqual(contract.state, "active")

    def test_legacy_contract_write_meta(self):
        contract = self.env["rental.subrent.contract"].create({
            "supplier_id": self.supplier.id,
            "policy_code": "simple",
            "company_id": self.company.id,
            "line_ids": [(0, 0, {
                "product_tmpl_id": self.product.product_tmpl_id.id,
                "cost_unit": 1000.0,
            })],
        })
        contract.write({
            "contract_date": date(2026, 4, 1),
            "supplier_representative_id": self.supplier_rep.id,
        })
        self.assertEqual(contract.contract_date, date(2026, 4, 1))

    def test_form_arch_has_info_and_lines_pages(self):
        arch, _view = self.env["rental.subrent.contract"]._get_view(view_type="form")
        xml = etree.tostring(arch, encoding="unicode")
        self.assertIn('name="subrent_info"', xml)
        self.assertIn('name="subrent_lines"', xml)
        self.assertIn("supplier_representative_id", xml)
        self.assertIn("our_representative_id", xml)
        self.assertIn("contract_number", xml)
        self.assertIn("Đơn giá thuê NCC / tháng", xml)
