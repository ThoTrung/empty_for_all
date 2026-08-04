# -*- coding: utf-8 -*-
"""DEC-29 / 29b — multi-role partner test matrix (A–G)."""
from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.tools.safe_eval import safe_eval


@tagged("post_install", "-at_install", "partner_multi_role")
class PartnerMultiRoleCase(TransactionCase):
    """Shared helpers for multi-role partner tests."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.has_subrent = "rental.subrent.contract" in cls.env

    def _make_customer(self, name="KH Test"):
        return self.env["res.partner"].create({
            "name": name,
            "is_rental_customer": True,
            "company_id": self.company.id,
        })

    def _make_supplier(self, name="NCC Test"):
        return self.env["res.partner"].create({
            "name": name,
            "is_rental_supplier": True,
            "company_id": self.company.id,
        })

    def _make_dual(self, name="NCC kiêm KH"):
        return self.env["res.partner"].create({
            "name": name,
            "is_rental_customer": True,
            "is_rental_supplier": True,
            "company_id": self.company.id,
        })

    def _make_rep(self, parent, name="Rep"):
        return self.env["res.partner"].create({
            "name": name,
            "parent_id": parent.id,
        })

    def _make_rental_contract(self, customer, status="active"):
        rep = self._make_rep(customer, f"Rep {customer.name}")
        b_rep = self._make_rep(self.company.partner_id, f"B Rep {customer.id}")
        contract = self.env["rental.contract"].create({
            "a_company_party": customer.id,
            "a_party": rep.id,
            "b_company_party": self.company.partner_id.id,
            "b_party": b_rep.id,
            "minimum_rental_months": 0,
        })
        contract.status = status
        return contract

    def _make_subrent_contract(self, supplier, state="active"):
        product = self.env["product.product"].create({
            "name": f"SP Subrent {supplier.id}",
            "type": "product",
            "list_price": 1000.0,
        })
        contract = self.env["rental.subrent.contract"].create({
            "supplier_id": supplier.id,
            "policy_code": "simple",
            "company_id": self.company.id,
            "line_ids": [(0, 0, {
                "product_tmpl_id": product.product_tmpl_id.id,
                "cost_unit": 500.0,
            })],
        })
        if state == "active":
            contract.action_activate()
        return contract

    def _search_customers(self, partner):
        return self.env["res.partner"].search([
            ("is_rental_customer", "=", True),
            ("is_company", "=", True),
            ("id", "=", partner.id),
        ])

    def _search_suppliers(self, partner):
        return self.env["res.partner"].search([
            ("is_rental_supplier", "=", True),
            ("is_company", "=", True),
            ("id", "=", partner.id),
        ])

    def _action_context(self, xmlid):
        action = self.env.ref(xmlid, raise_if_not_found=False)
        if not action:
            return None
        ctx = action.context or {}
        if isinstance(ctx, str):
            normalized = " ".join(ctx.split())
            # Legacy bad XML stored "{ { ... }" (extra leading brace)
            while normalized.startswith("{ {"):
                normalized = normalized[1:].lstrip()
            ctx = safe_eval(normalized)
        return ctx

    def _eval_action_domain(self, xmlid):
        action = self.env.ref(xmlid, raise_if_not_found=False)
        if not action:
            return None
        domain = action.domain or []
        if isinstance(domain, str):
            domain = safe_eval(
                " ".join(domain.split()),
                {"allowed_company_ids": self.env.companies.ids},
            )
        return domain


class TestPartnerMultiRoleCreate(PartnerMultiRoleCase):
    """A — Create / defaults."""

    def test_a1_create_customer_only_forces_company(self):
        p = self._make_customer("A1 KH")
        self.assertTrue(p.is_company)
        self.assertEqual(p.customer_type, "company")
        self.assertTrue(p.is_rental_customer)
        self.assertFalse(p.is_rental_supplier)

    def test_a2_create_supplier_only_forces_company(self):
        p = self._make_supplier("A2 NCC")
        self.assertTrue(p.is_company)
        self.assertEqual(p.customer_type, "company")
        self.assertTrue(p.is_rental_supplier)
        self.assertFalse(p.is_rental_customer)

    def test_a3_create_dual_role(self):
        p = self._make_dual("A3 Dual")
        self.assertTrue(p.is_company)
        self.assertEqual(p.customer_type, "company")
        self.assertTrue(p.is_rental_customer)
        self.assertTrue(p.is_rental_supplier)

    def test_a4_create_other_without_role(self):
        p = self.env["res.partner"].create({
            "name": "A4 Other",
            "customer_type": "other",
            "company_id": self.company.id,
        })
        self.assertEqual(p.customer_type, "other")
        self.assertFalse(p.is_rental_customer)
        self.assertFalse(p.is_rental_supplier)

    def test_a5_create_driver_without_role(self):
        p = self.env["res.partner"].create({
            "name": "A5 Driver",
            "customer_type": "driver",
            "is_company": False,
            "company_id": self.company.id,
        })
        self.assertEqual(p.customer_type, "driver")
        self.assertFalse(p.is_company)
        self.assertFalse(p.is_rental_customer)

    def test_a6_renter_menu_action_defaults(self):
        ctx = self._action_context("rental.action_res_partner_renters")
        self.assertTrue(ctx.get("default_is_rental_customer"))
        self.assertEqual(ctx.get("default_customer_type"), "company")
        self.assertTrue(ctx.get("default_is_company"))

    def test_a7_supplier_menu_action_defaults(self):
        ctx = self._action_context(
            "rental_subrent.action_res_partner_rental_suppliers"
        )
        if ctx is None:
            self.skipTest("rental_subrent not installed")
        self.assertTrue(ctx.get("default_is_rental_supplier"))
        self.assertEqual(ctx.get("default_customer_type"), "company")
        self.assertTrue(ctx.get("default_is_company"))
        self.assertEqual(ctx.get("default_supplier_rank"), 1)


class TestPartnerMultiRoleAlign(PartnerMultiRoleCase):
    """B — Align / constrain."""

    def test_b1_enable_supplier_on_other_individual(self):
        p = self.env["res.partner"].create({
            "name": "B1 Other",
            "is_company": False,
            "customer_type": "other",
            "company_id": self.company.id,
        })
        p.write({"is_rental_supplier": True})
        self.assertTrue(p.is_company)
        self.assertEqual(p.customer_type, "company")
        self.assertTrue(p.is_rental_supplier)

    def test_b2_enable_customer_on_driver(self):
        p = self.env["res.partner"].create({
            "name": "B2 Driver",
            "is_company": False,
            "customer_type": "driver",
            "company_id": self.company.id,
        })
        p.write({"is_rental_customer": True})
        self.assertTrue(p.is_company)
        self.assertEqual(p.customer_type, "company")
        self.assertTrue(p.is_rental_customer)

    def test_b3_single_write_keeps_company_while_role_on(self):
        p = self._make_customer("B3 Stay")
        p.write({"customer_type": "driver", "is_company": False})
        self.assertTrue(p.is_company)
        self.assertEqual(p.customer_type, "company")
        self.assertTrue(p.is_rental_customer)

    def test_b4_multi_record_write_keeps_company_while_role_on(self):
        p1 = self._make_customer("B4a")
        p2 = self._make_supplier("B4b")
        (p1 | p2).write({"customer_type": "driver", "is_company": False})
        self.assertTrue(p1.is_company)
        self.assertEqual(p1.customer_type, "company")
        self.assertTrue(p2.is_company)
        self.assertEqual(p2.customer_type, "company")

    def test_b5_sql_inconsistent_state_raises_constrain(self):
        p = self._make_customer("B5 SQL")
        self.env.cr.execute(
            """
            UPDATE res_partner
               SET customer_type = 'driver',
                   is_company = FALSE
             WHERE id = %s
            """,
            (p.id,),
        )
        p.invalidate_recordset()
        with self.assertRaises(ValidationError):
            p._check_rental_roles_company_form()

    def test_b6_clear_roles_then_set_driver(self):
        p = self._make_customer("B6 Clear")
        p.with_context(rental_skip_role_clear_warn=True).write({
            "is_rental_customer": False,
            "is_rental_supplier": False,
        })
        p.write({
            "customer_type": "driver",
            "is_company": False,
        })
        self.assertEqual(p.customer_type, "driver")
        self.assertFalse(p.is_company)
        self.assertFalse(p.is_rental_customer)

    def test_ghost_company_without_role_allowed(self):
        """P1 documented: company form with no role is allowed (ghost)."""
        p = self.env["res.partner"].create({
            "name": "Ghost Co",
            "is_company": True,
            "customer_type": "company",
            "company_id": self.company.id,
        })
        self.assertFalse(p.is_rental_customer)
        self.assertFalse(p.is_rental_supplier)
        self.assertFalse(self._search_customers(p))
        self.assertFalse(self._search_suppliers(p))


class TestPartnerMultiRoleDomain(PartnerMultiRoleCase):
    """C — Domain / picker / menu."""

    def test_c1_c2_dual_in_both_searches(self):
        p = self._make_dual("C Dual")
        self.assertEqual(self._search_customers(p), p)
        self.assertEqual(self._search_suppliers(p), p)

    def test_c3_pure_ncc_not_in_customer_search(self):
        p = self._make_supplier("C3 NCC")
        self.assertFalse(self._search_customers(p))
        self.assertEqual(self._search_suppliers(p), p)

    def test_c4_pure_kh_not_in_supplier_search(self):
        p = self._make_customer("C4 KH")
        self.assertEqual(self._search_customers(p), p)
        self.assertFalse(self._search_suppliers(p))

    def test_c5_a_company_party_fields_get_domain(self):
        info = self.env["rental.contract"].fields_get(
            ["a_company_party"], attributes=["domain"]
        )
        domain = info["a_company_party"].get("domain") or ""
        domain_str = domain if isinstance(domain, str) else str(domain)
        self.assertIn("is_rental_customer", domain_str)

    def test_c6_supplier_id_fields_get_domain(self):
        if not self.has_subrent:
            self.skipTest("rental_subrent not installed")
        info = self.env["rental.subrent.contract"].fields_get(
            ["supplier_id"], attributes=["domain"]
        )
        domain = info["supplier_id"].get("domain") or ""
        domain_str = domain if isinstance(domain, str) else str(domain)
        self.assertIn("is_rental_supplier", domain_str)

    def test_c7_menu_action_domains_include_exclude(self):
        kh = self._make_customer("C7 KH")
        ncc = self._make_supplier("C7 NCC")
        dual = self._make_dual("C7 Dual")

        kh_domain = self._eval_action_domain("rental.action_res_partner_renters")
        self.assertIsNotNone(kh_domain)
        found_kh = self.env["res.partner"].search(
            kh_domain + [("id", "in", (kh | ncc | dual).ids)]
        )
        self.assertIn(kh, found_kh)
        self.assertIn(dual, found_kh)
        self.assertNotIn(ncc, found_kh)

        ncc_domain = self._eval_action_domain(
            "rental_subrent.action_res_partner_rental_suppliers"
        )
        if ncc_domain is None:
            return
        found_ncc = self.env["res.partner"].search(
            ncc_domain + [("id", "in", (kh | ncc | dual).ids)]
        )
        self.assertIn(ncc, found_ncc)
        self.assertIn(dual, found_ncc)
        self.assertNotIn(kh, found_ncc)

    def test_c8_rented_qty_wizard_rejects_non_customer(self):
        ghost = self.env["res.partner"].create({
            "name": "C8 Ghost",
            "is_company": True,
            "customer_type": "company",
            "company_id": self.company.id,
        })
        with self.assertRaises(ValidationError):
            self.env["rental.rented.qty.wizard"].create({
                "partner_company_id": ghost.id,
            })
        ok = self._make_customer("C8 OK")
        wiz = self.env["rental.rented.qty.wizard"].create({
            "partner_company_id": ok.id,
        })
        self.assertEqual(wiz.partner_company_id, ok)


class TestPartnerMultiRoleWarn(PartnerMultiRoleCase):
    """D — Soft warn when clearing role with active contracts."""

    def test_d1_clear_customer_with_active_contract_posts_chatter(self):
        p = self._make_customer("D1 KH")
        self._make_rental_contract(p, status="active")
        before = self.env["mail.message"].search_count([
            ("model", "=", "res.partner"),
            ("res_id", "=", p.id),
        ])
        p.write({"is_rental_customer": False})
        self.assertFalse(p.is_rental_customer)
        after_msgs = self.env["mail.message"].search([
            ("model", "=", "res.partner"),
            ("res_id", "=", p.id),
        ], order="id desc", limit=5)
        self.assertGreater(len(after_msgs), 0)
        bodies = " ".join(after_msgs.mapped("body") or [])
        self.assertIn("Khách thuê", bodies)
        self.assertGreaterEqual(
            self.env["mail.message"].search_count([
                ("model", "=", "res.partner"),
                ("res_id", "=", p.id),
            ]),
            before,
        )

    def test_d2_clear_customer_with_new_contract_no_required_warn(self):
        p = self._make_customer("D2 KH")
        self._make_rental_contract(p, status="new")
        before = self.env["mail.message"].search_count([
            ("model", "=", "res.partner"),
            ("res_id", "=", p.id),
            ("body", "ilike", "Khách thuê"),
        ])
        p.write({"is_rental_customer": False})
        after = self.env["mail.message"].search_count([
            ("model", "=", "res.partner"),
            ("res_id", "=", p.id),
            ("body", "ilike", "%Đã tắt «Khách thuê»%"),
        ])
        self.assertEqual(after, before)

    def test_d3_clear_supplier_with_active_subrent_posts_chatter(self):
        if not self.has_subrent:
            self.skipTest("rental_subrent not installed")
        p = self._make_supplier("D3 NCC")
        self._make_subrent_contract(p, state="active")
        p.write({"is_rental_supplier": False})
        self.assertFalse(p.is_rental_supplier)
        msgs = self.env["mail.message"].search([
            ("model", "=", "res.partner"),
            ("res_id", "=", p.id),
            ("body", "ilike", "NCC"),
        ], limit=5)
        self.assertTrue(any("Đã tắt" in (m.body or "") for m in msgs))

    def test_d4_clear_supplier_without_contract_no_warn_message(self):
        p = self._make_supplier("D4 NCC")
        before = self.env["mail.message"].search_count([
            ("model", "=", "res.partner"),
            ("res_id", "=", p.id),
            ("body", "ilike", "%Đã tắt «NCC»%"),
        ])
        p.write({"is_rental_supplier": False})
        after = self.env["mail.message"].search_count([
            ("model", "=", "res.partner"),
            ("res_id", "=", p.id),
            ("body", "ilike", "%Đã tắt «NCC»%"),
        ])
        self.assertEqual(after, before)

    def test_d5_skip_warn_context(self):
        p = self._make_customer("D5 KH")
        self._make_rental_contract(p, status="active")
        before = self.env["mail.message"].search_count([
            ("model", "=", "res.partner"),
            ("res_id", "=", p.id),
            ("body", "ilike", "%Đã tắt «Khách thuê»%"),
        ])
        p.with_context(rental_skip_role_clear_warn=True).write({
            "is_rental_customer": False,
        })
        after = self.env["mail.message"].search_count([
            ("model", "=", "res.partner"),
            ("res_id", "=", p.id),
            ("body", "ilike", "%Đã tắt «Khách thuê»%"),
        ])
        self.assertEqual(after, before)

    def test_d6_onchange_clear_customer_returns_warning(self):
        p = self._make_customer("D6 KH")
        self._make_rental_contract(p, status="active")
        warning = self.env["res.partner"]._rental_build_role_clear_warning(
            p,
            clearing_customer=True,
            clearing_supplier=False,
        )
        self.assertTrue(warning)
        self.assertIn("Khách thuê", warning["message"])
        self.assertIsNone(
            self.env["res.partner"]._rental_build_role_clear_warning(
                p,
                clearing_customer=False,
                clearing_supplier=False,
            )
        )


class TestPartnerMultiRoleBusiness(PartnerMultiRoleCase):
    """E — Dual-role business flows."""

    def test_e1_ncc_add_customer_enters_both(self):
        p = self._make_supplier("E1 NCC")
        p.write({"is_rental_customer": True})
        self.assertEqual(self._search_customers(p), p)
        self.assertEqual(self._search_suppliers(p), p)

    def test_e2_kh_add_supplier_enters_both(self):
        p = self._make_customer("E2 KH")
        p.write({"is_rental_supplier": True})
        self.assertEqual(self._search_customers(p), p)
        self.assertEqual(self._search_suppliers(p), p)

    def test_e3_dual_clear_customer_keeps_supplier(self):
        p = self._make_dual("E3 Dual")
        p.with_context(rental_skip_role_clear_warn=True).write({
            "is_rental_customer": False,
        })
        self.assertFalse(self._search_customers(p))
        self.assertEqual(self._search_suppliers(p), p)

    def test_e4_dual_clear_supplier_keeps_customer(self):
        p = self._make_dual("E4 Dual")
        p.with_context(rental_skip_role_clear_warn=True).write({
            "is_rental_supplier": False,
        })
        self.assertEqual(self._search_customers(p), p)
        self.assertFalse(self._search_suppliers(p))

    def test_e5_rental_contract_with_dual_as_a_company(self):
        p = self._make_dual("E5 Dual")
        contract = self._make_rental_contract(p, status="new")
        self.assertEqual(contract.a_company_party, p)

    def test_e6_subrent_contract_with_dual_as_supplier(self):
        if not self.has_subrent:
            self.skipTest("rental_subrent not installed")
        p = self._make_dual("E6 Dual")
        contract = self._make_subrent_contract(p, state="draft")
        self.assertEqual(contract.supplier_id, p)


class TestPartnerMultiRoleView(PartnerMultiRoleCase):
    """F — View / action smoke."""

    def test_f1_form_arch_has_vai_tro_group(self):
        arch, _view = self.env["res.partner"]._get_view(view_type="form")
        arch_xml = arch if isinstance(arch, str) else arch.getroottree().getroot()
        from lxml import etree
        if not isinstance(arch_xml, str):
            xml = etree.tostring(arch, encoding="unicode")
        else:
            xml = arch_xml
        self.assertIn("Vai trò", xml)
        self.assertIn('name="is_rental_customer"', xml)
        self.assertIn('name="is_rental_supplier"', xml)

    def test_f2_no_dead_cho_thue_page(self):
        arch, _view = self.env["res.partner"]._get_view(view_type="form")
        from lxml import etree
        xml = etree.tostring(arch, encoding="unicode")
        # Dead page was only invisible customer_type under string Cho thuê
        self.assertNotIn('string="Cho thuê"', xml)

    def test_f3_customer_type_label_kieu_form(self):
        info = self.env["res.partner"].fields_get(
            ["customer_type"], attributes=["string"]
        )
        self.assertEqual(info["customer_type"]["string"], "Kiểu form")


class TestPartnerMultiRoleRegression(PartnerMultiRoleCase):
    """G — Isolation / driver smoke."""

    def test_g1_driver_name_search_excludes_company_role(self):
        company_p = self._make_customer("G1 Company Role")
        driver = self.env["res.partner"].create({
            "name": "G1 Driver Role",
            "customer_type": "driver",
            "is_company": False,
            "company_id": self.company.id,
        })
        names = self.env["res.partner"].name_search(
            "G1",
            args=[
                ("customer_type", "=", "driver"),
                ("is_company", "=", False),
            ],
            operator="ilike",
            limit=50,
        )
        ids = {pid for pid, _name in names}
        self.assertIn(driver.id, ids)
        self.assertNotIn(company_p.id, ids)

    def test_g2_create_role_stamps_company_id(self):
        p = self.env["res.partner"].create({
            "name": "G2 Stamp",
            "is_rental_customer": True,
        })
        self.assertEqual(p.company_id, self.company)
