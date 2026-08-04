# -*- coding: utf-8 -*-

from odoo.tests import tagged
from odoo.tests.common import TransactionCase, new_test_user


@tagged("post_install", "-at_install")
class TestPartnerCompanyIsolation(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_a = cls.env.company
        cls.company_b = cls.env["res.company"].create({
            "name": "Partner Isolation Co B",
        })

        cls.partner_a = cls.env["res.partner"].create({
            "name": "Isolation Customer A",
            "is_company": True,
            "customer_type": "company",
            "is_rental_customer": True,
            "company_id": cls.company_a.id,
        })
        cls.partner_b = cls.env["res.partner"].sudo().create({
            "name": "Isolation Customer B",
            "is_company": True,
            "customer_type": "company",
            "is_rental_customer": True,
            "company_id": cls.company_b.id,
        })
        # Shared commercial partner (company_id cleared after create stamp).
        cls.partner_shared = cls.env["res.partner"].sudo().create({
            "name": "Isolation Shared Customer",
            "is_company": True,
            "customer_type": "company",
            "is_rental_customer": True,
        })
        cls.partner_shared.sudo().write({"company_id": False})

        cls.user_a = new_test_user(
            cls.env,
            login="partner_isolation_user_a",
            groups="base.group_user,sales_team.group_sale_salesman",
            company_id=cls.company_a.id,
            company_ids=[(6, 0, [cls.company_a.id])],
        )

    def test_create_stamps_company_id(self):
        partner = self.env["res.partner"].create({
            "name": "Created Without Company",
            "is_company": True,
        })
        self.assertEqual(partner.company_id, self.env.company)

    def test_create_inherits_parent_company(self):
        child = self.env["res.partner"].create({
            "name": "Child Of A",
            "parent_id": self.partner_a.id,
        })
        self.assertEqual(child.company_id, self.company_a)

    def test_user_a_sees_own_company_partner(self):
        Partner = self.env["res.partner"].with_user(self.user_a)
        found = Partner.search([("id", "=", self.partner_a.id)])
        self.assertEqual(found, self.partner_a)
        names = Partner.name_search("Isolation Customer A", operator="ilike", limit=20)
        self.assertTrue(any(pid == self.partner_a.id for pid, _name in names))

    def test_user_a_cannot_see_other_company_partner(self):
        Partner = self.env["res.partner"].with_user(self.user_a)
        found = Partner.search([("id", "=", self.partner_b.id)])
        self.assertFalse(found)
        names = Partner.name_search("Isolation Customer B", operator="ilike", limit=20)
        self.assertFalse(any(pid == self.partner_b.id for pid, _name in names))

    def test_user_a_cannot_see_shared_commercial_partner(self):
        Partner = self.env["res.partner"].with_user(self.user_a)
        found = Partner.search([("id", "=", self.partner_shared.id)])
        self.assertFalse(found)
        names = Partner.name_search("Isolation Shared Customer", operator="ilike", limit=20)
        self.assertFalse(any(pid == self.partner_shared.id for pid, _name in names))

    def test_user_a_still_sees_internal_partner(self):
        """Internal users (partner_share=False) remain visible for Discuss."""
        Partner = self.env["res.partner"].with_user(self.user_a)
        found = Partner.search([("id", "=", self.user_a.partner_id.id)])
        self.assertEqual(found, self.user_a.partner_id)

    def test_company_partner_stamped_and_readable(self):
        """res.company.partner_id must carry company_id so strict rule allows read."""
        self.assertEqual(
            self.company_b.partner_id.company_id,
            self.company_b,
            "create() must stamp company partner with that company",
        )
        user_b = new_test_user(
            self.env,
            login="partner_isolation_user_b",
            groups="base.group_user,sales_team.group_sale_salesman",
            company_id=self.company_b.id,
            company_ids=[(6, 0, [self.company_b.id])],
        )
        Partner = self.env["res.partner"].with_user(user_b).with_company(self.company_b)
        found = Partner.search([("id", "=", self.company_b.partner_id.id)])
        self.assertEqual(found, self.company_b.partner_id)
        # Reading fields must not raise AccessError (company form loads partner_id).
        self.assertEqual(found.name, self.company_b.partner_id.name)

    def test_partner_form_no_autocomplete_widget(self):
        """name/vat must not use IAP field_partner_autocomplete on partner forms."""
        arch, _view = self.env["res.partner"]._get_view(view_type="form")
        for node in arch.xpath("//field[@name='name']|//field[@name='vat']"):
            self.assertNotEqual(
                node.get("widget"),
                "field_partner_autocomplete",
                "Partner form must keep plain text/char inputs (DEC-25)",
            )
        for node in arch.xpath("//field[@name='name']"):
            self.assertEqual(node.get("widget"), "text")

    def test_driver_id_fields_get_domain(self):
        """Custom filter / form pickers must expose driver+company domain on fields_get."""
        info = self.env["rr.transport"].fields_get(["driver_id"], attributes=["domain"])
        domain = info["driver_id"].get("domain") or ""
        domain_str = domain if isinstance(domain, str) else str(domain)
        self.assertIn("customer_type", domain_str)
        self.assertIn("driver", domain_str)
        self.assertIn("is_company", domain_str)

    def test_name_search_driver_domain_excludes_renter(self):
        """name_search with driver domain must not return renter companies."""
        driver = self.env["res.partner"].create({
            "name": "Isolation Driver A",
            "is_company": False,
            "customer_type": "driver",
            "company_id": self.company_a.id,
        })
        Partner = self.env["res.partner"].with_user(self.user_a)
        driver_domain = [
            ("customer_type", "=", "driver"),
            ("is_company", "=", False),
            ("company_id", "in", [self.company_a.id]),
        ]
        names = Partner.name_search("Isolation", args=driver_domain, operator="ilike", limit=50)
        ids = {pid for pid, _name in names}
        self.assertIn(driver.id, ids)
        self.assertNotIn(self.partner_a.id, ids)

    def test_name_search_empty_args_returns_non_drivers(self):
        """Reproduce DomainSelector bug: empty args can suggest renters/companies."""
        names = self.env["res.partner"].name_search(
            "Isolation Customer A", args=[], operator="ilike", limit=30
        )
        ids = {pid for pid, _name in names}
        self.assertIn(self.partner_a.id, ids)

    def test_name_search_with_driver_domain_matches_ui_fix(self):
        driver = self.env["res.partner"].create({
            "name": "Isolation Driver Filter",
            "is_company": False,
            "customer_type": "driver",
            "company_id": self.company_a.id,
        })
        names = self.env["res.partner"].name_search(
            "",
            args=[("customer_type", "=", "driver"), ("is_company", "=", False)],
            operator="ilike",
            limit=50,
        )
        ids = {pid for pid, _name in names}
        self.assertIn(driver.id, ids)
        self.assertNotIn(self.partner_a.id, ids)
        # No company-type renters.
        for pid in ids:
            p = self.env["res.partner"].browse(pid)
            self.assertEqual(p.customer_type, "driver")
            self.assertFalse(p.is_company)

    def test_a_company_party_fields_get_domain(self):
        info = self.env["rental.contract"].fields_get(
            ["a_company_party"], attributes=["domain"]
        )
        domain = info["a_company_party"].get("domain") or ""
        domain_str = domain if isinstance(domain, str) else str(domain)
        self.assertIn("is_rental_customer", domain_str)
        self.assertIn("is_company", domain_str)
