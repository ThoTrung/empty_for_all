# -*- coding: utf-8 -*-

from odoo.tests.common import TransactionCase


class TestConstructionWorkAddress(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        company = cls.env.company
        cls._a_company = cls.env["res.partner"].create({
            "name": "CW Address Renter",
            "is_company": True,
            "customer_type": "company",
            "is_rental_customer": True,
        })
        cls._a_party = cls.env["res.partner"].create({
            "name": "CW Address A rep",
            "parent_id": cls._a_company.id,
        })
        cls._b_party = cls.env["res.partner"].create({
            "name": "CW Address B rep",
            "parent_id": company.partner_id.id,
        })
        cls._project = cls.env["construction.project"].create({
            "name": "Dự án test CW",
            "company_id": company.id,
        })
        cls._address = cls.env["construction.address"].create({
            "name": "Địa điểm: 1 Test Street",
            "company_id": company.id,
        })
        cls._work = cls.env["construction.work"].create({
            "name": "Gói thầu test CW",
            "project_id": cls._project.id,
            "address_ids": [(6, 0, [cls._address.id])],
            "company_id": company.id,
        })
        cls._contract = cls.env["rental.contract"].create({
            "a_company_party": cls._a_company.id,
            "a_party": cls._a_party.id,
            "b_company_party": company.partner_id.id,
            "b_party": cls._b_party.id,
            "construction_work_id": cls._work.id,
        })

    def test_address_computed_from_work(self):
        self.assertEqual(
            self._contract.construction_work_address,
            "Địa điểm: 1 Test Street",
        )
        self.assertEqual(self._contract.construction_work_project_id, self._project)

    def test_address_syncs_when_address_name_changes(self):
        self._address.name = "Địa điểm: 99 New Road"
        self.assertEqual(
            self._contract.construction_work_address,
            "Địa điểm: 99 New Road",
        )

    def test_address_syncs_when_address_ids_change(self):
        other = self.env["construction.address"].create({
            "name": "Site B",
            "company_id": self.env.company.id,
        })
        self._work.address_ids = [(6, 0, [self._address.id, other.id])]
        lines = self._contract.construction_work_address.split("\n")
        self.assertEqual(len(lines), 2)
        self.assertEqual(set(lines), {"Địa điểm: 1 Test Street", "Site B"})
        self.assertEqual(
            set(self._contract.construction_work_address_ids.mapped("name")),
            {"Địa điểm: 1 Test Street", "Site B"},
        )
