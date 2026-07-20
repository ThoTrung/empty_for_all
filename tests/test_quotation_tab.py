# -*- coding: utf-8 -*-
from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase


class TestQuotationTab(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        company = cls.env.company
        cls._a_company = cls.env["res.partner"].create({
            "name": "Quote Tab Renter",
            "is_company": True,
            "customer_type": "renter",
        })
        cls._a_party = cls.env["res.partner"].create({
            "name": "Quote A rep",
            "parent_id": cls._a_company.id,
        })
        cls._b_party = cls.env["res.partner"].create({
            "name": "Quote B rep",
            "parent_id": company.partner_id.id,
        })
        cls._product_a = cls.env["product.product"].create({
            "name": "Quote Product A",
            "type": "product",
            "list_price": 3000.0,
            "compensation_price": 100.0,
        })
        cls._product_b = cls.env["product.product"].create({
            "name": "Quote Product B",
            "type": "product",
            "list_price": 1500.0,
            "compensation_price": 50.0,
        })
        cls._contract = cls.env["rental.contract"].create({
            "a_company_party": cls._a_company.id,
            "a_party": cls._a_party.id,
            "b_company_party": company.partner_id.id,
            "b_party": cls._b_party.id,
            "status": "new",
        })
        cls._line = cls.env["rental.contract.line"].create({
            "contract_id": cls._contract.id,
            "product_tmpl_id": cls._product_a.product_tmpl_id.id,
            "price_unit": 3000.0,
            "compensation_price": 200.0,
        })
        cls._template_set = cls.env["rental.product.template.set"].create({
            "name": "Mẫu báo giá test",
            "company_id": company.id,
            "line_ids": [
                (0, 0, {
                    "product_tmpl_id": cls._product_b.product_tmpl_id.id,
                    "price_unit": 1500.0,
                    "compensation_price": 50.0,
                }),
            ],
        })

    def test_unique_product_tmpl_per_contract(self):
        with self.assertRaises(ValidationError):
            self.env["rental.contract.line"].create({
                "contract_id": self._contract.id,
                "product_tmpl_id": self._product_a.product_tmpl_id.id,
                "price_unit": 1.0,
            })

    def test_locked_contract_blocks_line_write(self):
        self._contract.write({"status": "active", "edit_unlocked": False})
        self.assertFalse(self._contract.can_edit)
        with self.assertRaises(UserError):
            self._line.write({"price_unit": 999.0})
        with self.assertRaises(UserError):
            self.env["rental.contract.line"].create({
                "contract_id": self._contract.id,
                "product_tmpl_id": self._product_b.product_tmpl_id.id,
                "price_unit": 1.0,
            })

    def test_locked_contract_blocks_price_change(self):
        self._contract.write({"status": "active", "edit_unlocked": False})
        with self.assertRaises(UserError):
            self.env["rental.contract.line.price"].create({
                "contract_line_id": self._line.id,
                "date_from": "2026-02-01",
                "price_unit": 2800.0,
            })

    def test_locked_allow_context_bypasses_line_lock(self):
        self._contract.write({"status": "active", "edit_unlocked": False})
        self._line.with_context(rental_contract_allow_locked_write=True).write({
            "price_unit": 3100.0,
        })
        self.assertAlmostEqual(self._line.price_unit, 3100.0)

    def test_apply_product_list_template_replaces_lines(self):
        self._contract.write({
            "product_list_template_id": self._template_set.id,
            "status": "new",
        })
        self._contract.action_apply_product_list_template()
        lines = self._contract.rental_contract_line_ids
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines.product_tmpl_id, self._product_b.product_tmpl_id)
        self.assertAlmostEqual(lines.price_unit, 1500.0)

    def test_apply_template_requires_selection(self):
        self._contract.product_list_template_id = False
        with self.assertRaises(UserError):
            self._contract.action_apply_product_list_template()

    def test_quotation_monthly_day_export_math(self):
        """Document export mapping: month=price_unit, day=price_unit/30 (DEC-11)."""
        monthly = self._line.price_unit
        self.assertAlmostEqual(monthly, 3000.0)
        self.assertAlmostEqual(monthly / 30.0, 100.0)
        compensation = self._line.compensation_price or self._line.product_tmpl_id.compensation_price
        self.assertAlmostEqual(compensation, 200.0)
        self.assertAlmostEqual(self._line.price_unit_day, 100.0)

    def test_quotation_xlsx_placeholder_formats(self):
        self._contract.write({
            "contract_date": "2026-07-05",
            "minimum_rental_months": 2,
            "transport_fee_share_min_months": 11,
            "prices_include_tax": True,
        })
        replacements = self._contract._quotation_xlsx_placeholder_replacements()
        self.assertEqual(replacements["{{contract_date}}"], "ngày 05 tháng 07 năm 2026")
        self.assertEqual(replacements["{{minimum_rental_months}}"], "02")
        self.assertEqual(replacements["{{minimum_rental_months_to_day}}"], "60")
        self.assertEqual(replacements["{{transport_fee_share_min_months}}"], "11")
        self.assertEqual(replacements["{{transport_fee_share_min_months_to_day}}"], "330")
        self.assertEqual(replacements["{{prices_include_tax}}"], "đã")

        self._contract.prices_include_tax = False
        replacements = self._contract._quotation_xlsx_placeholder_replacements()
        self.assertEqual(replacements["{{prices_include_tax}}"], "chưa")
        self.assertEqual(
            self.env["rental.contract"]._format_months_padded(0),
            "00",
        )
