# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestBookingRouteMenuDomains(TransactionCase):
    def test_booking_form_domains_use_spa_allowed_staff_levels_context(self):
        view = self.env.ref("booking_calendar.view_spa_service_booking_form")
        arch = view.arch_db or ""
        self.assertIn("spa_allowed_staff_levels", arch)
        # card_id domain must filter by required staff level group
        self.assertIn("product_id.spa_required_staff_level_id.level_group", arch)
        # staff_ids domain must filter by user staff level group
        self.assertIn("spa_staff_level_id.level_group", arch)
        # booking_board stays in form but hidden (set via menu context only)
        self.assertRegex(arch, r'name="booking_board"[^>]*invisible="1"')

    def test_booking_line_modal_domain_uses_spa_allowed_staff_levels_context(self):
        view = self.env.ref("booking_calendar.view_spa_service_booking_line_form")
        arch = view.arch_db or ""
        self.assertIn("spa_allowed_staff_levels", arch)
        self.assertIn("spa_staff_level_id.level_group", arch)

    def test_doctor_and_specialist_actions_use_booking_board(self):
        doctor = self.env.ref("booking_calendar.action_spa_service_booking_doctor")
        specialist = self.env.ref("booking_calendar.action_spa_service_booking_specialist")
        self.assertIn("booking_board", doctor.domain or "")
        self.assertIn("'doctor'", doctor.domain or "")
        self.assertIn("default_booking_board", doctor.context or "")
        self.assertIn("booking_board", specialist.domain or "")
        self.assertIn("'specialist'", specialist.domain or "")
        self.assertIn("default_booking_board", specialist.context or "")
        self.assertNotIn("is_doctor_route", doctor.domain or "")
        self.assertNotIn("is_doctor_route", specialist.domain or "")

