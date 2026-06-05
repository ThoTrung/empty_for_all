# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase


class TestAmountToTextVI(TransactionCase):
    def test_no_khong_tram_on_leading_group(self):
        text = self.env["amount_to_text.vi"].vn_amount_to_text(25482356)
        self.assertNotIn("Không trăm", text)
        self.assertIn("Hai mươi lăm triệu", text)
        self.assertIn("ba trăm năm mươi sáu", text)

    def test_khong_tram_on_middle_group_when_needed(self):
        text = self.env["amount_to_text.vi"].vn_amount_to_text(1025000)
        self.assertIn("không trăm", text.casefold())
