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

    def test_parse_length_meters(self):
        self.assertEqual(rtm._parse_length_meters("2m"), 2.0)
        self.assertEqual(rtm._parse_length_meters("1,5m"), 1.5)
        self.assertEqual(rtm._parse_length_meters("0.9m"), 0.9)
        self.assertIsNone(rtm._parse_length_meters("Kích chân D38* L500"))

    def test_sum_linear_meters(self):
        cell = {10: 200, 11: 200}
        order = [10, 11]
        lengths = {10: 1.5, 11: 2.0}
        self.assertEqual(rtm._sum_linear_meters(cell, order, lengths), 700.0)

    def test_sort_products_by_length_label(self):
        prods = OrderedDict(
            [
                (1, {"variant_name": "2m", "prod_name": "Hộp (2m)"}),
                (2, {"variant_name": "1,5m", "prod_name": "Hộp (1,5m)"}),
                (3, {"variant_name": "0,9m", "prod_name": "Hộp (0,9m)"}),
            ]
        )
        sorted_o = rtm._sort_products_odict(prods)
        self.assertEqual(list(sorted_o.keys()), [3, 2, 1])
