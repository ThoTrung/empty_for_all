# -*- coding: utf-8 -*-
import re
from odoo import api, fields, models


class WebsitePopup(models.Model):
    _name = "website.popup"
    _description = "Website Popup"
    _order = "sequence asc, id desc"

    name = fields.Char(required=True, default="New Popup")
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)

    website_id = fields.Many2one(
        "website",
        string="Website",
        required=True,
        default=lambda self: self.env["website"].get_current_website(),
    )

    # Content
    title = fields.Char(string="Title")
    body_html = fields.Html(string="Content", sanitize=True)
    cover_image = fields.Image(string="Cover Image", max_width=1920, max_height=1920)

    primary_button_label = fields.Char(string="Primary Button Label", default="OK")
    primary_button_url = fields.Char(string="Primary Button URL")

    # Display config
    delay_ms = fields.Integer(string="Delay (ms)", default=500)

    show_frequency = fields.Selection(
        [
            ("always", "Every visit"),
            ("session", "Once per session"),
            ("ever", "Once ever"),
            ("days", "Once per N days"),
        ],
        default="session",
        required=True,
    )
    frequency_days = fields.Integer(string="N days", default=7)

    # Schedule
    date_start = fields.Datetime(string="Start (optional)")
    date_end = fields.Datetime(string="End (optional)")

    # Page targeting
    url_mode = fields.Selection(
        [
            ("all", "All pages"),
            ("contains", "URL contains"),
            ("regex", "URL regex"),
        ],
        default="all",
        required=True,
    )
    url_contains = fields.Char(string="URL contains")
    url_regex = fields.Char(string="URL regex")

    def _match_url(self, path: str) -> bool:
        self.ensure_one()
        path = path or ""
        if self.url_mode == "all":
            return True
        if self.url_mode == "contains":
            return True if not self.url_contains else (self.url_contains in path)
        if self.url_mode == "regex":
            if not self.url_regex:
                return True
            try:
                return re.search(self.url_regex, path) is not None
            except re.error:
                return False
        return True

    def _match_schedule(self, now_dt) -> bool:
        self.ensure_one()
        if self.date_start and now_dt < self.date_start:
            return False
        if self.date_end and now_dt > self.date_end:
            return False
        return True

    def to_public_dict(self):
        self.ensure_one()
        return {
            "id": self.id,
            "name": self.name or "",
            "title": self.title or "",
            "body_html": self.body_html or "",
            "image_url": "",  # filled by controller
            "primary_button_label": self.primary_button_label or "OK",
            "primary_button_url": self.primary_button_url or "",
            "delay_ms": int(self.delay_ms or 0),
            "show_frequency": self.show_frequency,
            "frequency_days": int(self.frequency_days or 0),
        }

    @api.model
    def get_first_eligible_popup(self, website, path: str):
        """
        Server-side selection of first eligible popup (by sequence).
        Frequency (local/session/ever/days) is handled on client side.
        """
        now = fields.Datetime.now()
        popups = self.sudo().search(
            [("active", "=", True), ("website_id", "=", website.id)],
            order="sequence asc, id desc",
        )
        for p in popups:
            if p._match_schedule(now) and p._match_url(path):
                return p
        return self.browse()
