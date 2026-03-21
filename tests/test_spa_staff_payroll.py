# -*- coding: utf-8 -*-

from datetime import date

from odoo import fields
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestSpaStaffPayroll(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.partner = cls.env["res.partner"].create({"name": "Payroll Test Partner"})
        cls.user = cls.env["res.users"].create({
            "name": "Therapist Payroll",
            "login": "therapist_payroll_test",
            "email": "tp@test.local",
            "groups_id": [(6, 0, [cls.env.ref("base.group_user").id])],
        })
        cls.employee = cls.env["hr.employee"].create({
            "name": "Therapist Payroll",
            "user_id": cls.user.id,
            "company_id": cls.company.id,
        })
        cls.contract = cls.env["hr.contract"].create({
            "name": "Test Contract",
            "employee_id": cls.employee.id,
            "date_start": date(2020, 1, 1),
            "wage": 10000000,
            "spa_overtime_hourly_rate": 100000,
            "state": "open",
        })
        cls.product_tmpl = cls.env["product.template"].create({
            "name": "Payroll Service Product",
            "detailed_type": "service",
            "spa_sessions_per_unit": 5,
            "service_employee_salary": 500000,
        })
        cls.product = cls.product_tmpl.product_variant_id
        cls.card = cls.env["spa.treatment.card"].create({
            "partner_id": cls.partner.id,
            "product_id": cls.product.id,
            "total_sessions": 10,
        })

    def test_session_split_creates_service_line(self):
        Session = self.env["spa.treatment.session"]
        session = Session.create({
            "card_id": self.card.id,
            "date": fields.Datetime.to_datetime(date(2025, 6, 15)),
            "therapist_id": self.user.id,
            "therapist_ids": [(6, 0, [self.user.id])],
            "duration_minutes": 60,
            "state": "done",
        })
        self.assertTrue(session.product_id)

        payroll = self.env["spa.staff.payroll"].create({
            "employee_id": self.employee.id,
            "company_id": self.company.id,
            "date_from": date(2025, 6, 1),
            "date_to": date(2025, 6, 30),
            "wage_fixed": self.contract.wage,
            "overtime_hourly_rate": self.contract.spa_overtime_hourly_rate,
            "currency_id": self.company.currency_id.id,
        })
        payroll.action_recompute_service_lines()
        self.assertEqual(len(payroll.service_line_ids), 1)
        self.assertEqual(payroll.service_line_ids.amount_share, 500000.0)

    def test_overtime_approved_in_payroll(self):
        ot = self.env["spa.staff.overtime.request"].create({
            "employee_id": self.employee.id,
            "overtime_date": date(2025, 6, 10),
            "hours": 2.0,
            "state": "submitted",
        })
        ot.sudo().action_approve()
        payroll = self.env["spa.staff.payroll"].create({
            "employee_id": self.employee.id,
            "company_id": self.company.id,
            "date_from": date(2025, 6, 1),
            "date_to": date(2025, 6, 30),
            "wage_fixed": self.contract.wage,
            "overtime_hourly_rate": self.contract.spa_overtime_hourly_rate,
            "currency_id": self.company.currency_id.id,
        })
        payroll.action_recompute_overtime_lines()
        self.assertEqual(len(payroll.overtime_line_ids), 1)
        self.assertEqual(payroll.overtime_line_ids.amount_subtotal, 200000.0)
