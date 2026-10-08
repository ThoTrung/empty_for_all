# -*- coding: utf-8 -*-
from datetime import date

from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase

from odoo.addons.rental_subrent.services.subrent_policies import (
    get_policy,
    list_policies,
    selection_list,
)


class TestSubrentPolicyRegistry(TransactionCase):
    def test_registry_has_three_policies(self):
        codes = {p.code for p in list_policies()}
        self.assertEqual(codes, {"simple", "tracked", "pass_through"})
        self.assertEqual(len(selection_list()), 3)
        self.assertEqual(get_policy("simple").code, "simple")


class TestSubrentSimpleMode(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        company = cls.env.company
        cls.company = company
        cls.supplier = cls.env["res.partner"].create({
            "name": "NCC Simple",
            "is_company": True,
            "customer_type": "company",
            "is_rental_supplier": True,
            "company_id": company.id,
        })
        cls.product = cls.env["product.product"].create({
            "name": "SP Simple",
            "type": "product",
            "list_price": 3000.0,
        })
        cls.contract = cls.env["rental.subrent.contract"].create({
            "supplier_id": cls.supplier.id,
            "policy_code": "simple",
            "date_start": date(2026, 1, 1),
            "company_id": company.id,
            "line_ids": [(0, 0, {
                "product_tmpl_id": cls.product.product_tmpl_id.id,
                "cost_unit": 2000.0,
            })],
        })
        cls.contract.action_activate()

    def _receive(self, qty=10):
        receipt = self.env["rental.subrent.receipt"].create({
            "subrent_contract_id": self.contract.id,
            "date": date(2026, 1, 1),
            "stock_flow": "into_stock",
            "company_id": self.company.id,
            "line_ids": [(0, 0, {"product_id": self.product.id, "qty": qty})],
        })
        receipt.action_confirm()
        return receipt

    def test_simple_receive_updates_obligation_no_lot(self):
        self._receive(10)
        line = self.contract.line_ids[:1]
        self.assertEqual(line.qty_received, 10)
        self.assertEqual(line.qty_open, 10)
        self.assertFalse(self.contract.lot_ids)
        self.assertEqual(line.amount_monthly_estimate, 20000.0)

    def test_simple_return_when_surplus(self):
        self._receive(10)
        ret = self.env["rental.subrent.return"].create({
            "subrent_contract_id": self.contract.id,
            "date": date(2026, 2, 1),
            "company_id": self.company.id,
            "line_ids": [(0, 0, {"product_id": self.product.id, "qty": 4})],
        })
        ret.action_confirm()
        line = self.contract.line_ids[:1]
        self.assertEqual(line.qty_open, 6)
        self.assertEqual(line.qty_returned, 4)

    def test_simple_return_over_open_blocked(self):
        self._receive(3)
        ret = self.env["rental.subrent.return"].create({
            "subrent_contract_id": self.contract.id,
            "date": date(2026, 2, 1),
            "company_id": self.company.id,
            "line_ids": [(0, 0, {"product_id": self.product.id, "qty": 5})],
        })
        with self.assertRaises(ValidationError):
            ret.action_confirm()

    def test_payable_wizard(self):
        self._receive(5)
        wiz = self.env["rental.subrent.payable.wizard"].create({
            "company_id": self.company.id,
            "date_from": date(2026, 1, 1),
            "date_to": date(2026, 1, 31),
            "subrent_contract_id": self.contract.id,
        })
        wiz.action_compute()
        self.assertEqual(wiz.amount_total, 10000.0)
        self.assertEqual(len(wiz.line_ids), 1)

    def test_cannot_change_policy_after_receive(self):
        self._receive(1)
        with self.assertRaises(UserError):
            self.contract.write({"policy_code": "tracked"})

    def test_ui_flags_simple(self):
        self.assertTrue(self.contract.show_obligation_ui)
        self.assertFalse(self.contract.show_lot_ui)
        self.assertFalse(self.contract.require_transport_lot)
