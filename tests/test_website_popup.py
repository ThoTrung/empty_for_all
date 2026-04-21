from datetime import timedelta

from odoo import fields
from odoo.tests.common import TransactionCase


class TestWebsitePopup(TransactionCase):
    def setUp(self):
        super().setUp()
        self.website = self.env["website"].search([], limit=1)
        self.Popup = self.env["website.popup"]

    def _create_popup(self, **vals):
        values = {
            "name": "Popup",
            "website_id": self.website.id,
            "url_mode": "all",
            "show_frequency": "session",
        }
        values.update(vals)
        return self.Popup.create(values)

    def test_match_url_contains_and_regex(self):
        popup_contains = self._create_popup(url_mode="contains", url_contains="/tin-tuc")
        self.assertTrue(popup_contains._match_url("/tin-tuc/abc"))
        self.assertFalse(popup_contains._match_url("/gallery"))

        popup_regex = self._create_popup(url_mode="regex", url_regex=r"^/gallery(/|$)")
        self.assertTrue(popup_regex._match_url("/gallery"))
        self.assertFalse(popup_regex._match_url("/tin-tuc"))

        popup_invalid_regex = self._create_popup(url_mode="regex", url_regex=r"(")
        self.assertFalse(popup_invalid_regex._match_url("/gallery"))

    def test_match_schedule(self):
        now = fields.Datetime.now()
        popup_started = self._create_popup(date_start=now - timedelta(days=1), date_end=now + timedelta(days=1))
        self.assertTrue(popup_started._match_schedule(now))

        popup_future = self._create_popup(date_start=now + timedelta(days=1))
        self.assertFalse(popup_future._match_schedule(now))

        popup_ended = self._create_popup(date_end=now - timedelta(days=1))
        self.assertFalse(popup_ended._match_schedule(now))

    def test_get_first_eligible_popup(self):
        self._create_popup(name="Late", sequence=20, url_mode="contains", url_contains="/tin-tuc")
        expected = self._create_popup(name="First", sequence=10, url_mode="all")

        popup = self.Popup.get_first_eligible_popup(self.website, "/gallery")
        self.assertEqual(popup, expected)
