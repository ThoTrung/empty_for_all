# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from lxml import etree


@tagged("post_install", "-at_install", "subrent_partner_tabs")
class TestSubrentPartnerContractTabs(TransactionCase):
    """Phase 0 — partner form tabs gated by rental roles."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company

    def test_subrent_o2m_create_from_partner(self):
        ncc = self.env["res.partner"].create({
            "name": "Phase0 NCC",
            "is_rental_supplier": True,
            "company_id": self.company.id,
        })
        contract = self.env["rental.subrent.contract"].create({
            "supplier_id": ncc.id,
            "policy_code": "simple",
            "company_id": self.company.id,
        })
        self.assertIn(contract, ncc.subrent_contract_ids)
        self.assertEqual(contract.supplier_id, ncc)

    def test_form_arch_tabs_role_invisible(self):
        arch, _view = self.env["res.partner"]._get_view(view_type="form")
        xml = etree.tostring(arch, encoding="unicode")
        self.assertIn('name="company_rental_contract_ids"', xml)
        self.assertIn("not is_rental_customer", xml)
        self.assertIn('name="company_subrent_contract_ids"', xml)
        self.assertIn("not is_rental_supplier", xml)
        self.assertIn("subrent_contract_ids", xml)
