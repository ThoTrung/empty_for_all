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

    def test_booking_line_modal_domain_uses_spa_allowed_staff_levels_context(self):
        view = self.env.ref("booking_calendar.view_spa_service_booking_line_form")
        arch = view.arch_db or ""
        self.assertIn("spa_allowed_staff_levels", arch)
        self.assertIn("spa_staff_level_id.level_group", arch)

