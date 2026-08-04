# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.rental.services import rental_contract_services as rcs

# Reuse snapshot within this window unless force=True.
ON_HIRE_SNAPSHOT_TTL_MINUTES = 15
# Cron keeps today + this many past as-of dates.
ON_HIRE_SNAPSHOT_RETENTION_DAYS = 14


class RentalAnalyticsOnHireLine(models.Model):
    """Snapshot of products still on hire / at customer as of a date.

    Materialized from the official LIFO engine (DEC-17), not stock.quant.
    Cached per company + as_of_date (TTL); refreshed from Dashboard / detail action.
    """

    _name = "rental.analytics.on.hire.line"
    _description = "Thống kê: sản phẩm đang thuê theo ngày"
    _order = "partner_company_id, construction_work_id, rental_contract_id, product_tmpl_id"
    _rec_name = "product_tmpl_id"

    company_id = fields.Many2one(
        "res.company",
        required=True,
        index=True,
        ondelete="cascade",
    )
    as_of_date = fields.Date(string="Ngày tra cứu", required=True, index=True)
    computed_at = fields.Datetime(
        string="Tính lúc",
        required=True,
        index=True,
        default=fields.Datetime.now,
    )
    partner_company_id = fields.Many2one(
        "res.partner",
        string="Khách hàng",
        required=True,
        index=True,
        ondelete="cascade",
        domain="[('is_rental_customer', '=', True), ('is_company', '=', True)]",
    )
    construction_work_id = fields.Many2one(
        "construction.work",
        string="Gói thầu / Công trình",
        index=True,
        ondelete="set null",
    )
    construction_project_id = fields.Many2one(
        "construction.project",
        string="Dự án",
        index=True,
        ondelete="set null",
    )
    rental_contract_id = fields.Many2one(
        "rental.contract",
        string="Hợp đồng",
        required=True,
        index=True,
        ondelete="cascade",
    )
    product_tmpl_id = fields.Many2one(
        "product.template",
        string="Sản phẩm",
        required=True,
        index=True,
        ondelete="cascade",
    )
    uom_id = fields.Many2one(
        "uom.uom",
        string="ĐVT",
        index=True,
        ondelete="restrict",
    )
    uom_name = fields.Char(string="ĐVT (text)")
    rented_qty = fields.Float(
        string="SL đang thuê",
        digits="Product Unit of Measure",
    )
    excess_qty = fields.Float(
        string="SL chuyển thừa",
        digits="Product Unit of Measure",
    )
    physical_qty = fields.Float(
        string="SL vật lý tại KH",
        digits="Product Unit of Measure",
    )

    _sql_constraints = [
        (
            "uniq_on_hire_snapshot_line",
            "unique(company_id, as_of_date, rental_contract_id, product_tmpl_id)",
            "Dòng snapshot SL đang thuê bị trùng (công ty/ngày/HĐ/SP).",
        ),
    ]

    @api.model
    def _snapshot_domain(self, as_of_date):
        return [
            ("company_id", "in", self.env.companies.ids),
            ("as_of_date", "=", as_of_date),
        ]

    @api.model
    def _snapshot_is_fresh(self, as_of_date, ttl_minutes=ON_HIRE_SNAPSHOT_TTL_MINUTES):
        line = self.search(
            self._snapshot_domain(as_of_date),
            order="computed_at desc",
            limit=1,
        )
        if not line or not line.computed_at:
            return False
        age = fields.Datetime.now() - fields.Datetime.to_datetime(line.computed_at)
        return age.total_seconds() < float(ttl_minutes) * 60.0

    @api.model
    def ensure_snapshot(
        self,
        as_of_date,
        *,
        force=False,
        ttl_minutes=ON_HIRE_SNAPSHOT_TTL_MINUTES,
        only_active_contracts=True,
    ):
        """Return company snapshot lines for ``as_of_date``, refreshing if stale."""
        if not as_of_date:
            raise UserError(_("Ngày tra cứu là bắt buộc."))
        as_of_date = fields.Date.to_date(as_of_date)
        if not force and self._snapshot_is_fresh(as_of_date, ttl_minutes=ttl_minutes):
            return self.search(self._snapshot_domain(as_of_date))
        return self.refresh_for_date(
            as_of_date,
            only_active_contracts=only_active_contracts,
        )

    @api.model
    def refresh_for_date(
        self,
        as_of_date,
        *,
        only_active_contracts=True,
    ):
        """Replace full snapshot rows for current companies at ``as_of_date``."""
        if not as_of_date:
            raise UserError(_("Ngày tra cứu là bắt buộc."))
        as_of_date = fields.Date.to_date(as_of_date)

        company_ids = self.env.companies.ids
        self.search([
            ("company_id", "in", company_ids),
            ("as_of_date", "=", as_of_date),
        ]).unlink()

        rows = rcs.calc_rented_qty_as_of(
            self.env,
            as_of_date,
            only_active_contracts=only_active_contracts,
        )
        if not rows:
            return self.browse()

        contracts = self.env["rental.contract"].browse(
            {row["contract_id"] for row in rows}
        )
        company_by_contract = {
            contract.id: contract.company_id.id for contract in contracts
        }
        tmpls = self.env["product.template"].browse(
            {row["tmpl_id"] for row in rows}
        )
        uom_by_tmpl = {tmpl.id: tmpl.uom_id for tmpl in tmpls}
        now = fields.Datetime.now()
        vals_list = []
        for row in rows:
            uom = uom_by_tmpl.get(row["tmpl_id"])
            vals_list.append({
                "company_id": company_by_contract[row["contract_id"]],
                "as_of_date": as_of_date,
                "computed_at": now,
                "partner_company_id": row["partner_company_id"],
                "construction_work_id": row.get("construction_work_id") or False,
                "construction_project_id": row.get("construction_project_id") or False,
                "rental_contract_id": row["contract_id"],
                "product_tmpl_id": row["tmpl_id"],
                "uom_id": uom.id if uom else False,
                "uom_name": row["uom_name"] or (uom.name if uom else ""),
                "rented_qty": row["rented_qty"],
                "excess_qty": row["excess_qty"],
                "physical_qty": row["physical_qty"],
            })
        return self.create(vals_list)

    @api.model
    def search_snapshot(
        self,
        as_of_date,
        *,
        partner_company_id=None,
        construction_work_id=None,
        partner_company_ids=None,
        construction_work_ids=None,
        force=False,
        only_active_contracts=True,
    ):
        """Ensure snapshot then optionally filter by customer(s) / site(s)."""
        lines = self.ensure_snapshot(
            as_of_date,
            force=force,
            only_active_contracts=only_active_contracts,
        )
        domain = list(self._snapshot_domain(as_of_date))
        partner_ids = list(partner_company_ids or [])
        if not partner_ids and partner_company_id:
            partner_ids = [partner_company_id]
        work_ids = list(construction_work_ids or [])
        if not work_ids and construction_work_id:
            work_ids = [construction_work_id]
        if partner_ids:
            domain.append(("partner_company_id", "in", partner_ids))
        if work_ids:
            domain.append(("construction_work_id", "in", work_ids))
        return self.search(domain)

    @api.model
    def action_open_on_hire_detail(self):
        """Menu/server entry: refresh today's snapshot if needed, then open views."""
        as_of = fields.Date.context_today(self)
        force = bool(self.env.context.get("analytics_force_refresh"))
        self.ensure_snapshot(as_of, force=force)
        computed = self.search(
            self._snapshot_domain(as_of),
            order="computed_at desc",
            limit=1,
        ).computed_at
        return {
            "type": "ir.actions.act_window",
            "name": _("SL đang thuê (chi tiết)"),
            "res_model": self._name,
            "view_mode": "graph,tree,pivot",
            "views": [
                (self.env.ref("rental.view_rental_analytics_on_hire_graph").id, "graph"),
                (self.env.ref("rental.view_rental_analytics_on_hire_tree").id, "list"),
                (self.env.ref("rental.view_rental_analytics_on_hire_pivot").id, "pivot"),
            ],
            "domain": self._snapshot_domain(as_of),
            "context": {
                "analytics_as_of_date": fields.Date.to_string(as_of),
                "search_default_group_partner": 1,
                "analytics_computed_at": fields.Datetime.to_string(computed)
                if computed
                else False,
            },
        }

    @api.model
    def _cron_cleanup_old_snapshots(self):
        cutoff = fields.Date.context_today(self) - timedelta(
            days=ON_HIRE_SNAPSHOT_RETENTION_DAYS
        )
        old = self.search([("as_of_date", "<", cutoff)])
        old.unlink()
        return True
