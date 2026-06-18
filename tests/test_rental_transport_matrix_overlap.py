# -*- coding: utf-8 -*-

from collections import OrderedDict
from datetime import date

from odoo.addons.rental.models import rental_transport_matrix as rtm
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestRentalTransportMatrixOverlap(TransactionCase):
    """Overlap rules for rental.transport.matrix on the same rental.contract."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        company = cls.env.company
        cls._a_company = cls.env["res.partner"].create(
            {
                "name": "Test Renter Co (matrix overlap)",
                "is_company": True,
                "customer_type": "renter",
            }
        )
        cls._a_party = cls.env["res.partner"].create(
            {
                "name": "Test A representative",
                "parent_id": cls._a_company.id,
            }
        )
        cls._b_company = company.partner_id
        cls._b_party = cls.env["res.partner"].create(
            {
                "name": "Test B representative (matrix overlap)",
                "parent_id": cls._b_company.id,
            }
        )

    def _new_contract(self):
        return self.env["rental.contract"].create(
            {
                "a_company_party": self._a_company.id,
                "a_party": self._a_party.id,
                "b_company_party": self._b_company.id,
                "b_party": self._b_party.id,
            }
        )

    def test_matrix_constraint_rejects_overlap(self):
        contract = self._new_contract()
        Matrix = self.env["rental.transport.matrix"]
        Matrix.create(
            {
                "rental_contract_id": contract.id,
                "start_date": date(2026, 1, 1),
                "end_date": date(2026, 1, 31),
                "name": "M1",
            }
        )
        with self.assertRaises(ValidationError):
            Matrix.create(
                {
                    "rental_contract_id": contract.id,
                    "start_date": date(2026, 1, 15),
                    "end_date": date(2026, 2, 15),
                    "name": "M2 overlap",
                }
            )

    def test_matrix_constraint_allows_adjacent_ranges(self):
        contract = self._new_contract()
        Matrix = self.env["rental.transport.matrix"]
        Matrix.create(
            {
                "rental_contract_id": contract.id,
                "start_date": date(2026, 1, 1),
                "end_date": date(2026, 1, 31),
                "name": "Jan",
            }
        )
        Matrix.create(
            {
                "rental_contract_id": contract.id,
                "start_date": date(2026, 2, 1),
                "end_date": date(2026, 2, 28),
                "name": "Feb",
            }
        )

    def test_action_create_transport_matrix_returns_wizard_when_overlap(self):
        contract = self._new_contract()
        self.env["rental.transport.matrix"].create(
            {
                "rental_contract_id": contract.id,
                "start_date": date(2026, 3, 1),
                "end_date": date(2026, 3, 31),
                "name": "Existing",
            }
        )
        action = contract.action_create_transport_matrix_record(
            date(2026, 3, 10),
            date(2026, 4, 10),
        )
        self.assertEqual(action.get("type"), "ir.actions.act_window")
        self.assertEqual(action.get("res_model"), "rental.transport.matrix.overlap.wizard")
        self.assertEqual(action.get("target"), "new")
        wiz = self.env["rental.transport.matrix.overlap.wizard"].browse(action["res_id"])
        self.assertTrue(wiz.exists())
        self.assertEqual(wiz.rental_contract_id, contract)

    def test_action_create_transport_matrix_opens_matrix_when_no_overlap(self):
        contract = self._new_contract()
        self.env["rental.transport.matrix"].create(
            {
                "rental_contract_id": contract.id,
                "start_date": date(2026, 5, 1),
                "end_date": date(2026, 5, 31),
                "name": "May",
            }
        )
        action = contract.action_create_transport_matrix_record(
            date(2026, 6, 1),
            date(2026, 6, 30),
        )
        self.assertEqual(action.get("type"), "ir.actions.act_window")
        self.assertEqual(action.get("res_model"), "rental.transport.matrix")
        self.assertEqual(action.get("target"), "current")
        matrix = self.env["rental.transport.matrix"].browse(action["res_id"])
        self.assertTrue(matrix.exists())
        self.assertEqual(matrix.rental_contract_id, contract)
        self.assertEqual(matrix.start_date, date(2026, 6, 1))
        self.assertEqual(matrix.end_date, date(2026, 6, 30))

    def test_overlap_wizard_opens_same_action_as_smart_button(self):
        contract = self._new_contract()
        wiz = self.env["rental.transport.matrix.overlap.wizard"].create(
            {"rental_contract_id": contract.id}
        )
        from_wizard = wiz.action_open_transport_matrices()
        from_contract = contract.action_open_transport_matrices()
        self.assertEqual(from_wizard.get("type"), from_contract.get("type"))
        self.assertEqual(from_wizard.get("res_model"), from_contract.get("res_model"))
        self.assertEqual(from_wizard.get("domain"), from_contract.get("domain"))
        self.assertEqual(
            from_wizard.get("context", {}).get("default_rental_contract_id"),
            from_contract.get("context", {}).get("default_rental_contract_id"),
        )


class TestRentalTransportMatrixHelpers(TransactionCase):
    """Pure helpers: length parsing, MD sum, variant sort order."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        md_categ = cls.env["uom.category"].create({"name": "Test length MD"})
        unit_categ = cls.env["uom.category"].create({"name": "Test unit MD"})
        cls._uom_linear_meter = cls.env["uom.uom"].create({
            "name": "Mét dài (test)",
            "category_id": md_categ.id,
            "uom_type": "reference",
            "is_linear_meter_variant": True,
        })
        cls._uom_piece = cls.env["uom.uom"].create({
            "name": "Cái (test)",
            "category_id": unit_categ.id,
            "uom_type": "reference",
            "is_linear_meter_variant": False,
        })
        cls._product_linear_meter = cls.env["product.template"].create({
            "name": "Hộp 5*10 (test MD)",
            "type": "product",
            "uom_id": cls._uom_linear_meter.id,
            "uom_po_id": cls._uom_linear_meter.id,
        }).product_variant_ids[0]
        cls._product_piece = cls.env["product.template"].create({
            "name": "Kích chân D38* L500 (test)",
            "type": "product",
            "uom_id": cls._uom_piece.id,
            "uom_po_id": cls._uom_piece.id,
        }).product_variant_ids[0]

    def test_variant_price_multiplier_from_ptav(self):
        attr = self.env["product.attribute"].create(
            {"name": "Length (test MD)", "create_variant": "always"}
        )
        val_15 = self.env["product.attribute.value"].create(
            {
                "name": "1,5m",
                "attribute_id": attr.id,
                "default_price_multiplier": 1.5,
            }
        )
        val_20 = self.env["product.attribute.value"].create(
            {
                "name": "2m",
                "attribute_id": attr.id,
                "default_price_multiplier": 2.0,
            }
        )
        tmpl = self.env["product.template"].create(
            {
                "name": "Hộp 5*10 (test MD variants)",
                "type": "product",
                "uom_id": self._uom_linear_meter.id,
                "uom_po_id": self._uom_linear_meter.id,
                "attribute_line_ids": [
                    (
                        0,
                        0,
                        {
                            "attribute_id": attr.id,
                            "value_ids": [(6, 0, [val_15.id, val_20.id])],
                        },
                    )
                ],
            }
        )
        by_mult = {
            rtm._variant_price_multiplier(v): v
            for v in tmpl.product_variant_ids
        }
        self.assertEqual(by_mult[1.5].product_template_attribute_value_ids.price_multiplier, 1.5)
        self.assertEqual(by_mult[2.0].product_template_attribute_value_ids.price_multiplier, 2.0)
        self.assertEqual(rtm._linear_meter_factor_for_product(by_mult[1.5]), 1.5)
        self.assertEqual(rtm._linear_meter_factor_for_product(self._product_piece), None)

    def test_sum_linear_meters(self):
        cell = {10: 200, 11: 200}
        order = [10, 11]
        lengths = {10: 1.5, 11: 2.0}
        self.assertEqual(rtm._sum_linear_meters(cell, order, lengths), 700.0)

    def test_sort_products_by_price_multiplier(self):
        prods = OrderedDict(
            [
                (1, {"variant_name": "2m", "prod_name": "Hộp (2m)", "price_multiplier": 2.0}),
                (2, {"variant_name": "1,5m", "prod_name": "Hộp (1,5m)", "price_multiplier": 1.5}),
                (3, {"variant_name": "0,9m", "prod_name": "Hộp (0,9m)", "price_multiplier": 0.9}),
            ]
        )
        sorted_o = rtm._sort_products_odict(prods)
        self.assertEqual(list(sorted_o.keys()), [3, 2, 1])

    def test_group_needs_md_single_variant_linear_meter_uom(self):
        pid = self._product_linear_meter.id
        prods = {pid: {"variant_name": "1,5m", "prod_name": "Hộp 5*10 (1,5m)"}}
        self.assertTrue(rtm._group_needs_md_column(self.env, prods, [pid]))

    def test_group_needs_md_single_variant_non_linear_meter_uom(self):
        pid = self._product_piece.id
        prods = {pid: {"variant_name": "", "prod_name": "Kích chân D38* L500"}}
        self.assertFalse(rtm._group_needs_md_column(self.env, prods, [pid]))

    def test_group_needs_md_multi_variant_linear_meter_uom(self):
        pid = self._product_linear_meter.id
        prods = {
            pid: {"variant_name": "1,5m", "prod_name": "Hộp (1,5m)"},
            pid + 1: {"variant_name": "2m", "prod_name": "Hộp (2m)"},
        }
        self.assertTrue(rtm._group_needs_md_column(self.env, prods, [pid, pid + 1]))

    def test_group_needs_md_multi_variant_non_linear_meter_uom(self):
        pid = self._product_piece.id
        prods = {
            pid: {"variant_name": "Size A", "prod_name": "Kích chân (A)"},
            pid + 1: {"variant_name": "Size B", "prod_name": "Kích chân (B)"},
        }
        self.assertFalse(rtm._group_needs_md_column(self.env, prods, [pid, pid + 1]))
