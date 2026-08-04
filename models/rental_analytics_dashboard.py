# -*- coding: utf-8 -*-
from collections import defaultdict

from odoo import _, api, fields, models
from odoo.tools.misc import format_date, formatLang

from odoo.addons.rental.services import rental_stock_xnt as stock_xnt


def _as_id_list(value):
    """Normalize singular id / list of ids from dashboard filters."""
    if not value:
        return []
    if isinstance(value, (list, tuple, set)):
        return [int(v) for v in value if v]
    return [int(value)]


class RentalAnalyticsDashboard(models.AbstractModel):
    """Analytics Hub shell: widget registry + summary RPC for the OWL dashboard.

    Add a future widget by extending ``_iter_widget_builders``.
    """

    _name = "rental.analytics.dashboard"
    _description = "Bảng thống kê cho thuê"

    @api.model
    def get_filter_options(self):
        """Partners / sites / warehouses for dashboard filters."""
        company_ids = self.env.companies.ids
        partners = self.env["res.partner"].search([
            ("is_company", "=", True),
            ("is_rental_customer", "=", True),
            ("company_id", "in", company_ids),
        ], order="name")
        works = self.env["construction.work"].search([
            ("company_id", "in", company_ids),
        ], order="name")
        warehouses = self.env["stock.warehouse"].search([
            ("company_id", "in", company_ids),
        ], order="name")
        today = fields.Date.context_today(self)
        month_start = today.replace(day=1)
        return {
            "partners": [{"id": p.id, "name": p.display_name} for p in partners],
            "construction_works": [
                {"id": w.id, "name": w.display_name} for w in works
            ],
            "warehouses": [
                {"id": w.id, "name": w.display_name} for w in warehouses
            ],
            "default_as_of_date": fields.Date.to_string(today),
            "default_xnt_date_from": fields.Date.to_string(month_start),
            "default_xnt_date_to": fields.Date.to_string(today),
        }

    @api.model
    def _normalize_filters(self, filters=None):
        filters = dict(filters or {})
        as_of_date = fields.Date.to_date(
            filters.get("as_of_date") or fields.Date.context_today(self)
        )
        partner_company_ids = _as_id_list(
            filters.get("partner_company_ids")
            if "partner_company_ids" in filters
            else filters.get("partner_company_id")
        )
        construction_work_ids = _as_id_list(
            filters.get("construction_work_ids")
            if "construction_work_ids" in filters
            else filters.get("construction_work_id")
        )
        warehouse_ids = _as_id_list(filters.get("warehouse_ids"))
        only_active = bool(filters.get("only_active_contracts", True))
        return {
            "as_of_date": fields.Date.to_string(as_of_date),
            "partner_company_ids": partner_company_ids,
            "construction_work_ids": construction_work_ids,
            "warehouse_ids": warehouse_ids,
            "partner_company_id": partner_company_ids[0] if len(partner_company_ids) == 1 else False,
            "construction_work_id": (
                construction_work_ids[0] if len(construction_work_ids) == 1 else False
            ),
            "only_active_contracts": only_active,
        }

    @api.model
    def get_dashboard_data(self, filters=None):
        force = bool((filters or {}).get("force_refresh"))
        norm = self._normalize_filters(filters)
        as_of_date = fields.Date.to_date(norm["as_of_date"])
        widgets = []
        for builder in self._iter_widget_builders():
            widget = builder(norm, force=force)
            if widget:
                widgets.append(widget)
        widgets.sort(key=lambda w: w.get("sequence", 100))
        return {
            "filters": norm,
            "as_of_date_display": format_date(self.env, as_of_date),
            "widgets": widgets,
        }

    @api.model
    def get_xnt_summary(self, filters=None):
        """Period XNT KPIs + Nhập/Xuất chart for the dashboard block."""
        filters = dict(filters or {})
        norm = self._normalize_filters(filters)
        today = fields.Date.context_today(self)
        as_of = fields.Date.to_date(norm["as_of_date"])
        date_to = fields.Date.to_date(filters.get("date_to") or as_of or today)
        date_from = fields.Date.to_date(
            filters.get("date_from") or date_to.replace(day=1)
        )
        if date_from > date_to:
            date_from, date_to = date_to, date_from

        warehouse_ids = norm["warehouse_ids"] or None
        summary = stock_xnt.summarize_xnt_for_dashboard(
            self.env,
            date_from,
            date_to,
            company_ids=self.env.companies.ids,
            warehouse_ids=warehouse_ids,
        )
        return {
            "date_from": fields.Date.to_string(date_from),
            "date_to": fields.Date.to_string(date_to),
            "date_from_display": format_date(self.env, date_from),
            "date_to_display": format_date(self.env, date_to),
            "warehouse_ids": warehouse_ids or [],
            "totals_by_uom": summary["totals_by_uom"],
            "chart": {
                "type": "bar",
                "labels": summary["chart"]["labels"],
                "datasets": [
                    {
                        "label": _("Nhập"),
                        "data": summary["chart"]["in_values"],
                    },
                    {
                        "label": _("Xuất"),
                        "data": summary["chart"]["out_values"],
                    },
                ],
            },
            "empty_message": _("Không có xuất/nhập kho trong kỳ này."),
            "line_count": len(summary["lines"]),
        }

    @api.model
    def action_open_xnt_wizard(self, filters=None):
        filters = dict(filters or {})
        norm = self._normalize_filters(filters)
        as_of = fields.Date.to_date(norm["as_of_date"])
        today = fields.Date.context_today(self)
        date_to = fields.Date.to_date(filters.get("date_to") or as_of or today)
        date_from = fields.Date.to_date(
            filters.get("date_from") or date_to.replace(day=1)
        )
        return self.env["rental.stock.xnt.wizard"].action_open_wizard(
            date_from=date_from,
            date_to=date_to,
            warehouse_ids=norm["warehouse_ids"] or None,
        )

    def _iter_widget_builders(self):
        return [
            self._build_on_hire_by_product_widget,
            self._build_warehouse_stock_widget,
            self._build_receivable_widget,
        ]

    def _build_on_hire_by_product_widget(self, filters, force=False):
        OnHire = self.env["rental.analytics.on.hire.line"]
        as_of = fields.Date.to_date(filters["as_of_date"])
        partner_ids = _as_id_list(filters.get("partner_company_ids"))
        work_ids = _as_id_list(filters.get("construction_work_ids"))
        lines = OnHire.search_snapshot(
            as_of,
            partner_company_ids=partner_ids or None,
            construction_work_ids=work_ids or None,
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
        if partner_ids:
            domain.append(("partner_company_id", "in", partner_ids))
        if work_ids:
            domain.append(("construction_work_id", "in", work_ids))

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

    def _build_warehouse_stock_widget(self, filters, force=False):
        Onhand = self.env["rental.analytics.stock.onhand.line"]
        as_of = fields.Date.to_date(filters["as_of_date"])
        warehouse_ids = _as_id_list(filters.get("warehouse_ids"))
        lines = Onhand.ensure_snapshot(
            as_of,
            warehouse_ids=warehouse_ids or None,
            force=force,
        )

        by_uom = defaultdict(lambda: {
            "qty_on_hand": 0.0,
            "uom_name": "",
            "uom_id": False,
        })
        product_totals = defaultdict(lambda: {
            "qty_on_hand": 0.0,
            "name": "",
            "uom_name": "",
            "uom_id": False,
        })
        computed_at = False
        for line in lines:
            uom_key = line.uom_id.id or 0
            bucket = by_uom[uom_key]
            bucket["qty_on_hand"] += line.qty_on_hand
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
            pt["qty_on_hand"] += line.qty_on_hand
            pt["name"] = line.product_tmpl_id.display_name
            pt["uom_name"] = bucket["uom_name"]
            pt["uom_id"] = bucket["uom_id"]

        totals_by_uom = sorted(
            (
                {
                    "uom_id": data["uom_id"],
                    "uom_name": data["uom_name"],
                    "qty_on_hand": data["qty_on_hand"],
                }
                for data in by_uom.values()
            ),
            key=lambda row: (-row["qty_on_hand"], row["uom_name"]),
        )
        ranked = sorted(
            product_totals.values(),
            key=lambda row: (-row["qty_on_hand"], row["name"]),
        )[:12]
        labels = [
            "%s (%s)" % (row["name"], row["uom_name"]) for row in ranked
        ]
        values = [row["qty_on_hand"] for row in ranked]

        key = Onhand._warehouse_key(warehouse_ids)
        domain = [
            ("company_id", "in", self.env.companies.ids),
            ("as_of_date", "=", as_of),
            ("warehouse_key", "=", key),
        ]
        detail_action = {
            "type": "ir.actions.act_window",
            "name": _("Tồn kho theo sản phẩm"),
            "res_model": "rental.analytics.stock.onhand.line",
            "view_mode": "graph,list,pivot",
            "views": [
                (self.env.ref("rental.view_rental_analytics_stock_onhand_graph").id, "graph"),
                (self.env.ref("rental.view_rental_analytics_stock_onhand_tree").id, "list"),
                (self.env.ref("rental.view_rental_analytics_stock_onhand_pivot").id, "pivot"),
            ],
            "domain": domain,
            "context": {
                "analytics_as_of_date": filters["as_of_date"],
                "analytics_warehouse_ids": warehouse_ids,
                "search_default_group_product": 1,
            },
        }
        return {
            "key": "warehouse_stock",
            "title": _("Tồn kho"),
            "subtitle": _(
                "Tính đến %s · Không lọc theo KH/công trình"
            ) % format_date(self.env, as_of),
            "computed_at": fields.Datetime.to_string(computed_at)
            if computed_at
            else False,
            "sequence": 15,
            "total_label": False,
            "total_value": False,
            "totals_by_uom": [
                {
                    "uom_id": row["uom_id"],
                    "uom_name": row["uom_name"],
                    "physical_qty": row["qty_on_hand"],
                    "rented_qty": False,
                    "excess_qty": False,
                }
                for row in totals_by_uom
            ],
            "metrics": {
                "onhand_label": _("Tồn kho"),
            },
            "widget_kind": "warehouse_stock",
            "empty_message": _("Không có tồn kho tại ngày này."),
            "chart": {
                "type": "bar",
                "labels": labels,
                "values": values,
                "dataset_label": _("Tồn kho (theo từng ĐVT)"),
            },
            "detail_action": detail_action,
        }

    def _build_receivable_widget(self, filters, force=False):
        del force  # live residual; no snapshot
        Move = self.env["account.move"]
        partner_ids = _as_id_list(filters.get("partner_company_ids"))
        work_ids = _as_id_list(filters.get("construction_work_ids"))
        domain = [
            ("company_id", "in", self.env.companies.ids),
            ("move_type", "in", ("out_invoice", "out_refund")),
            ("state", "=", "posted"),
            ("rental_contract_id", "!=", False),
            ("amount_residual", "!=", 0),
        ]
        if partner_ids:
            domain.append(("rental_partner_company_id", "in", partner_ids))
        if work_ids:
            domain.append(("rental_construction_work_id", "in", work_ids))

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
