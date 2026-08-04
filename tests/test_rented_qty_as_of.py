# -*- coding: utf-8 -*-
from datetime import date

from odoo.addons.rental.services import rental_contract_services as rcs
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestRentedQtyAsOf(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        company = cls.env.company
        cls.customer = cls.env["res.partner"].create({
            "name": "As-of Customer",
            "is_company": True,
            "customer_type": "company",
            "is_rental_customer": True,
            "company_id": company.id,
        })
        cls.customer_rep = cls.env["res.partner"].create({
            "name": "As-of Customer Representative",
            "parent_id": cls.customer.id,
        })
        cls.supplier_rep = cls.env["res.partner"].create({
            "name": "As-of Supplier Representative",
            "parent_id": company.partner_id.id,
        })
        cls.driver = cls.env["res.partner"].create({
            "name": "As-of Driver",
            "customer_type": "driver",
        })
        cls.truck = cls.env["transport.truck"].create({
            "name": "51A-ASOF",
            "plate": "51A-ASOF",
            "company_id": company.id,
        })
        cls.product = cls.env["product.product"].create({
            "name": "As-of Product",
            "type": "product",
            "list_price": 3000.0,
        })
        cls.contract = cls._create_contract("As-of Contract 1")

    @classmethod
    def _create_contract(cls, name):
        contract = cls.env["rental.contract"].create({
            "name": name,
            "a_company_party": cls.customer.id,
            "a_party": cls.customer_rep.id,
            "b_company_party": cls.env.company.partner_id.id,
            "b_party": cls.supplier_rep.id,
            "minimum_rental_months": 0,
        })
        cls.env["rental.contract.line"].create({
            "contract_id": contract.id,
            "product_tmpl_id": cls.product.product_tmpl_id.id,
            "price_unit": 3000.0,
        })
        contract.status = "active"
        return contract

    def _make_transport(
        self,
        contract,
        transport_type,
        when,
        qty,
        *,
        non_billable_qty=0,
        state="done",
    ):
        return self.env["rr.transport"].create({
            "rental_contract_id": contract.id,
            "type": transport_type,
            "state": state,
            "start_rental_or_return_date": when,
            "driver_id": self.driver.id,
            "transport_truck_id": self.truck.id,
            "vehicle_start_time": when,
            "transport_line_ids": [(0, 0, {
                "product_id": self.product.id,
                "qty": qty,
                "non_billable_qty": non_billable_qty,
            })],
        })

    def _rows(self, as_of_date, **kwargs):
        return rcs.calc_rented_qty_as_of(
            self.env,
            as_of_date,
            contract_ids=kwargs.pop("contract_ids", self.contract.ids),
            **kwargs,
        )

    def test_delivery_is_rented_at_end_of_day(self):
        self._make_transport(
            self.contract, "delivery", date(2026, 1, 1), 100
        )
        row = self._rows(date(2026, 1, 1))[0]
        self.assertEqual(row["rented_qty"], 100)
        self.assertEqual(row["excess_qty"], 0)
        self.assertEqual(row["physical_qty"], 100)

    def test_return_reduces_rented_quantity_as_of_return_date(self):
        self._make_transport(
            self.contract, "delivery", date(2026, 1, 1), 100
        )
        self._make_transport(
            self.contract, "return", date(2026, 1, 10), 40
        )
        self.assertEqual(self._rows(date(2026, 1, 9))[0]["rented_qty"], 100)
        self.assertEqual(self._rows(date(2026, 1, 10))[0]["rented_qty"], 60)

    def test_excess_is_separate_and_returned_first(self):
        self._make_transport(
            self.contract,
            "delivery",
            date(2026, 2, 1),
            100,
            non_billable_qty=20,
        )
        self._make_transport(
            self.contract, "return", date(2026, 2, 5), 10
        )
        row = self._rows(date(2026, 2, 5))[0]
        self.assertEqual(row["rented_qty"], 80)
        self.assertEqual(row["excess_qty"], 10)
        self.assertEqual(row["physical_qty"], 90)

    def test_draft_transport_is_excluded_until_done(self):
        transport = self._make_transport(
            self.contract,
            "delivery",
            date(2026, 3, 1),
            25,
            state="draft",
        )
        self.assertFalse(self._rows(date(2026, 3, 1)))
        transport.state = "done"
        self.assertEqual(self._rows(date(2026, 3, 1))[0]["rented_qty"], 25)

    def test_customer_scope_rolls_up_multiple_contracts(self):
        second_contract = self._create_contract("As-of Contract 2")
        self._make_transport(
            self.contract, "delivery", date(2026, 4, 1), 60
        )
        self._make_transport(
            second_contract, "delivery", date(2026, 4, 1), 90
        )
        rows = rcs.calc_rented_qty_as_of(
            self.env,
            date(2026, 4, 1),
            partner_company_ids=self.customer.ids,
            only_active_contracts=True,
        )
        self.assertEqual(len(rows), 2)
        self.assertEqual(sum(row["rented_qty"] for row in rows), 150)

    def test_result_matches_payment_block_present_total(self):
        self._make_transport(
            self.contract, "delivery", date(2026, 5, 1), 70
        )
        self._make_transport(
            self.contract, "return", date(2026, 5, 3), 15
        )
        as_of = date(2026, 5, 3)
        block = rcs.calc_rental_payment_blocks_by_template(
            self.env, self.contract, as_of, as_of
        )[0]
        row = self._rows(as_of)[0]
        self.assertEqual(row["rented_qty"], block["present_total_qty"])

    def test_wizard_populates_contract_result_lines(self):
        self._make_transport(
            self.contract, "delivery", date(2026, 6, 1), 35
        )
        wizard = self.env["rental.rented.qty.wizard"].create({
            "as_of_date": date(2026, 6, 1),
            "rental_contract_id": self.contract.id,
            "only_active_contracts": False,
        })

        action = wizard.action_compute()

        self.assertEqual(action["res_id"], wizard.id)
        self.assertEqual(len(wizard.line_ids), 1)
        self.assertEqual(wizard.line_ids.rented_qty, 35)
        self.assertEqual(
            wizard.line_ids.partner_company_id,
            self.customer,
        )

    def test_wizard_customer_is_limited_to_current_company_renters(self):
        domain = self.env[
            "rental.rented.qty.wizard"
        ]._fields["partner_company_id"].domain
        self.assertIn("('is_rental_customer', '=', True)", domain)
        self.assertIn("('company_id', '=', company_id)", domain)

        valid = self.env["rental.rented.qty.wizard"].create({
            "partner_company_id": self.customer.id,
        })
        self.assertEqual(valid.partner_company_id, self.customer)

        normal_company = self.env["res.partner"].create({
            "name": "Not a renter",
            "is_company": True,
            "company_id": self.env.company.id,
        })
        other_company = self.env["res.company"].create({
            "name": "Other rental company",
        })
        other_company_renter = self.env["res.partner"].create({
            "name": "Other company renter",
            "is_company": True,
            "customer_type": "company",
            "is_rental_customer": True,
            "company_id": other_company.id,
        })

        for invalid_partner in (
            self.env.company.partner_id,
            normal_company,
            other_company_renter,
        ):
            with self.subTest(partner=invalid_partner.display_name):
                with self.assertRaises(ValidationError):
                    self.env["rental.rented.qty.wizard"].create({
                        "partner_company_id": invalid_partner.id,
                    })
