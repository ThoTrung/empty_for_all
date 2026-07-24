# -*- coding: utf-8 -*-
from collections import defaultdict

from odoo import _, api, fields, models
from odoo.tools.misc import format_date, formatLang


class RentalAnalyticsDashboard(models.AbstractModel):
    """Analytics Hub shell: widget registry + summary RPC for the OWL dashboard.

    Add a future widget by extending ``_iter_widget_builders``.
    """

    _name = "rental.analytics.dashboard"
    _description = "Rental Analytics Dashboard"

    @api.model
    def get_filter_options(self):
        """Partners / sites for dashboard Many2one-like selects."""
        company_ids = self.env.companies.ids
        partners = self.env["res.partner"].search([
            ("is_company", "=", True),
            ("customer_type", "=", "renter"),
            ("company_id", "in", company_ids),
        ], order="name")
        works = self.env["construction.work"].search([
            ("company_id", "in", company_ids),
        ], order="name")
        return {
            "partners": [{"id": p.id, "name": p.display_name} for p in partners],
            "construction_works": [
                {"id": w.id, "name": w.display_name} for w in works
            ],
            "default_as_of_date": fields.Date.to_string(
                fields.Date.context_today(self)
            ),
        }

    @api.model
    def get_dashboard_data(self, filters=None):
        filters = dict(filters or {})
        as_of_date = fields.Date.to_date(
            filters.get("as_of_date") or fields.Date.context_today(self)
        )
        partner_company_id = filters.get("partner_company_id") or False
        construction_work_id = filters.get("construction_work_id") or False
        only_active = bool(filters.get("only_active_contracts", True))
        force = bool(filters.get("force_refresh"))

        norm = {
            "as_of_date": fields.Date.to_string(as_of_date),
            "partner_company_id": partner_company_id or False,
            "construction_work_id": construction_work_id or False,
            "only_active_contracts": only_active,
        }
        widgets = []
        for builder in self._iter_widget_builders():
            widget = builder(norm, force=force)
            if widget:
                widgets.append(widget)
        return {
            "filters": norm,
            "as_of_date_display": format_date(self.env, as_of_date),
            "widgets": widgets,
        }

    def _iter_widget_builders(self):
        return [
            self._build_on_hire_by_product_widget,
            self._build_receivable_widget,
        ]

    def _build_on_hire_by_product_widget(self, filters, force=False):
        OnHire = self.env["rental.analytics.on.hire.line"]
        as_of = fields.Date.to_date(filters["as_of_date"])
        lines = OnHire.search_snapshot(
            as_of,
            partner_company_id=filters.get("partner_company_id") or None,
            construction_work_id=filters.get("construction_work_id") or None,
            force=force,
            only_active_contracts=filters.get("only_active_contracts", True),
        )

        by_uom = defaultdict(lambda: {
            "rented_qty": 0.0,
            "excess_qty": 0.0,
            "physical_qty": 0.0,
            "uom_name": "",
            "uom_id": False,
        })
        # product totals kept per (tmpl, uom) — never cross-UoM
        product_totals = defaultdict(lambda: {
            "physical_qty": 0.0,
            "rented_qty": 0.0,
            "excess_qty": 0.0,
            "name": "",
            "uom_name": "",
            "uom_id": False,
            "tmpl_id": False,
        })
        computed_at = False
        for line in lines:
            uom_key = line.uom_id.id or 0
            bucket = by_uom[uom_key]
            bucket["rented_qty"] += line.rented_qty
            bucket["excess_qty"] += line.excess_qty
            bucket["physical_qty"] += line.physical_qty
            bucket["uom_name"] = line.uom_name or (
                line.uom_id.display_name if line.uom_id else _("(không ĐVT)")
            )
            bucket["uom_id"] = line.uom_id.id or False
            if not computed_at or (
                line.computed_at and line.computed_at > computed_at
            ):
                computed_at = line.computed_at

            pkey = (line.product_tmpl_id.id, uom_key)
            pt = product_totals[pkey]
            pt["physical_qty"] += line.physical_qty
            pt["rented_qty"] += line.rented_qty
            pt["excess_qty"] += line.excess_qty
            pt["name"] = line.product_tmpl_id.display_name
            pt["uom_name"] = bucket["uom_name"]
            pt["uom_id"] = bucket["uom_id"]
            pt["tmpl_id"] = line.product_tmpl_id.id

        totals_by_uom = sorted(
            (
                {
                    "uom_id": data["uom_id"],
                    "uom_name": data["uom_name"],
                    "rented_qty": data["rented_qty"],
                    "excess_qty": data["excess_qty"],
                    "physical_qty": data["physical_qty"],
                }
                for data in by_uom.values()
            ),
            key=lambda row: (-row["physical_qty"], row["uom_name"]),
        )

        # Chart: top products within each UoM (label includes UoM); no cross-UoM total.
        ranked = sorted(
            product_totals.values(),
            key=lambda row: (-row["physical_qty"], row["name"]),
        )[:12]
        labels = [
            "%s (%s)" % (row["name"], row["uom_name"]) for row in ranked
        ]
        values = [row["physical_qty"] for row in ranked]

        domain = [
            ("company_id", "in", self.env.companies.ids),
            ("as_of_date", "=", as_of),
        ]
        if filters.get("partner_company_id"):
            domain.append(
                ("partner_company_id", "=", filters["partner_company_id"])
            )
        if filters.get("construction_work_id"):
            domain.append(
                ("construction_work_id", "=", filters["construction_work_id"])
            )

        detail_action = {
            "type": "ir.actions.act_window",
            "name": _("SL đang thuê theo sản phẩm"),
            "res_model": "rental.analytics.on.hire.line",
            "view_mode": "graph,list,pivot",
            "views": [
                (self.env.ref("rental.view_rental_analytics_on_hire_graph").id, "graph"),
                (self.env.ref("rental.view_rental_analytics_on_hire_tree").id, "list"),
                (self.env.ref("rental.view_rental_analytics_on_hire_pivot").id, "pivot"),
            ],
            "domain": domain,
            "context": {
                "analytics_as_of_date": filters["as_of_date"],
                "search_default_group_partner": 1,
            },
        }
        return {
            "key": "on_hire_by_product",
            "title": _("SL sản phẩm đang thuê"),
            "subtitle": _("Tính đến %s") % format_date(self.env, as_of),
            "computed_at": fields.Datetime.to_string(computed_at)
            if computed_at
            else False,
            "sequence": 10,
            # No single cross-UoM total — use totals_by_uom + billable/excess.
            "total_label": False,
            "total_value": False,
            "totals_by_uom": totals_by_uom,
            "metrics": {
                "rented_label": _("Đang thuê (billable)"),
                "excess_label": _("Chuyển thừa"),
            },
            "empty_message": _("Không có sản phẩm đang thuê tại ngày này."),
            "chart": {
                "type": "bar",
                "labels": labels,
                "values": values,
                "dataset_label": _("SL vật lý tại KH (theo từng ĐVT)"),
            },
            "detail_action": detail_action,
        }

    def _build_receivable_widget(self, filters, force=False):
        del force  # live residual; no snapshot
        Move = self.env["account.move"]
        domain = [
            ("company_id", "in", self.env.companies.ids),
            ("move_type", "in", ("out_invoice", "out_refund")),
            ("state", "=", "posted"),
            ("rental_contract_id", "!=", False),
            ("amount_residual", "!=", 0),
        ]
        if filters.get("partner_company_id"):
            domain.append(
                ("rental_partner_company_id", "=", filters["partner_company_id"])
            )
        if filters.get("construction_work_id"):
            domain.append(
                ("rental_construction_work_id", "=", filters["construction_work_id"])
            )

        groups = Move.read_group(
            domain,
            ["amount_residual:sum", "rental_partner_company_id"],
            ["rental_partner_company_id"],
            orderby="amount_residual desc",
            lazy=False,
        )
        labels = []
        values = []
        total_due = 0.0
        for group in groups:
            partner = group.get("rental_partner_company_id")
            residual = group.get("amount_residual") or 0.0
            if not partner or not residual:
                continue
            labels.append(partner[1])
            values.append(residual)
            total_due += residual
        # Keep card readable
        labels = labels[:12]
        values = values[:12]

        currency = self.env.company.currency_id
        detail_action = {
            "type": "ir.actions.act_window",
            "name": _("Công nợ thuê"),
            "res_model": "account.move",
            "view_mode": "pivot,graph,tree,form",
            "views": [
                (self.env.ref("rental.view_rental_analytics_receivable_pivot").id, "pivot"),
                (self.env.ref("rental.view_rental_analytics_receivable_graph").id, "graph"),
                (False, "list"),
                (False, "form"),
            ],
            "domain": domain,
            "context": {
                "search_default_group_rental_partner": 1,
                "default_move_type": "out_invoice",
            },
        }
        return {
            "key": "receivable_by_partner",
            "title": _("Công nợ khách hàng"),
            "subtitle": _("Hóa đơn thuê còn phải thu"),
            "computed_at": False,
            "sequence": 20,
            "total_label": _("Tổng còn nợ"),
            "total_value": total_due,
            "total_value_display": formatLang(
                self.env, total_due, currency_obj=currency
            ),
            "totals_by_uom": [],
            "metrics": {},
            "empty_message": _("Không có công nợ thuê còn lại."),
            "chart": {
                "type": "bar",
                "labels": labels,
                "values": values,
                "dataset_label": _("Công nợ"),
            },
            "detail_action": detail_action,
        }
