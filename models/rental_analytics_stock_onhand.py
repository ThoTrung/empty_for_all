# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.rental.services import rental_stock_xnt as stock_xnt

ONHAND_SNAPSHOT_TTL_MINUTES = 15
ONHAND_SNAPSHOT_RETENTION_DAYS = 14


class RentalAnalyticsStockOnhandLine(models.Model):
    """Warehouse on-hand snapshot as of a date (from stock.move, not LIFO)."""

    _name = "rental.analytics.stock.onhand.line"
    _description = "Thống kê: tồn kho theo ngày"
    _order = "product_tmpl_id, product_id"
    _rec_name = "product_id"

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
    warehouse_key = fields.Char(
        string="Khóa lọc kho",
        required=True,
        index=True,
        default="all",
        help="Comma-separated warehouse ids or 'all'.",
    )
    product_id = fields.Many2one(
        "product.product",
        string="Biến thể",
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
    uom_id = fields.Many2one("uom.uom", string="ĐVT", ondelete="restrict")
    uom_name = fields.Char(string="ĐVT (text)")
    qty_on_hand = fields.Float(
        string="Tồn kho",
        digits="Product Unit of Measure",
    )

    _sql_constraints = [
        (
            "uniq_stock_onhand_snapshot_line",
            "unique(company_id, as_of_date, warehouse_key, product_id)",
            "Dòng snapshot tồn kho bị trùng.",
        ),
    ]

    @api.model
    def _warehouse_key(self, warehouse_ids=None):
        ids = sorted(int(i) for i in (warehouse_ids or []) if i)
        return ",".join(str(i) for i in ids) if ids else "all"

    @api.model
    def _snapshot_domain(self, as_of_date, warehouse_key="all"):
        return [
            ("company_id", "in", self.env.companies.ids),
            ("as_of_date", "=", as_of_date),
            ("warehouse_key", "=", warehouse_key),
        ]

    @api.model
    def _snapshot_is_fresh(self, as_of_date, warehouse_key="all", ttl_minutes=ONHAND_SNAPSHOT_TTL_MINUTES):
        line = self.search(
            self._snapshot_domain(as_of_date, warehouse_key),
            order="computed_at desc",
            limit=1,
        )
        if not line or not line.computed_at:
            return False
        age = fields.Datetime.now() - fields.Datetime.to_datetime(line.computed_at)
        return age.total_seconds() < float(ttl_minutes) * 60.0

    @api.model
    def ensure_snapshot(self, as_of_date, *, warehouse_ids=None, force=False):
        if not as_of_date:
            raise UserError(_("Ngày tra cứu là bắt buộc."))
        as_of_date = fields.Date.to_date(as_of_date)
        key = self._warehouse_key(warehouse_ids)
        if not force and self._snapshot_is_fresh(as_of_date, key):
            return self.search(self._snapshot_domain(as_of_date, key))
        return self.refresh_for_date(as_of_date, warehouse_ids=warehouse_ids)

    @api.model
    def refresh_for_date(self, as_of_date, *, warehouse_ids=None):
        if not as_of_date:
            raise UserError(_("Ngày tra cứu là bắt buộc."))
        as_of_date = fields.Date.to_date(as_of_date)
        key = self._warehouse_key(warehouse_ids)
        company_ids = self.env.companies.ids
        self.search([
            ("company_id", "in", company_ids),
            ("as_of_date", "=", as_of_date),
            ("warehouse_key", "=", key),
        ]).unlink()

        rows = stock_xnt.calc_stock_on_hand_as_of(
            self.env,
            as_of_date,
            company_ids=company_ids,
            warehouse_ids=warehouse_ids,
        )
        if not rows:
            return self.browse()

        now = fields.Datetime.now()
        vals_list = []
        for row in rows:
            vals_list.append({
                "company_id": row["company_id"] or self.env.company.id,
                "as_of_date": as_of_date,
                "computed_at": now,
                "warehouse_key": key,
                "product_id": row["product_id"],
                "product_tmpl_id": row["product_tmpl_id"],
                "uom_id": row["uom_id"],
                "uom_name": row["uom_name"],
                "qty_on_hand": row["qty_on_hand"],
            })
        return self.create(vals_list)

    @api.model
    def action_open_onhand_detail(self):
        as_of = fields.Date.context_today(self)
        force = bool(self.env.context.get("analytics_force_refresh"))
        warehouse_ids = self.env.context.get("analytics_warehouse_ids") or []
        self.ensure_snapshot(as_of, warehouse_ids=warehouse_ids, force=force)
        key = self._warehouse_key(warehouse_ids)
        return {
            "type": "ir.actions.act_window",
            "name": _("Tồn kho (chi tiết)"),
            "res_model": self._name,
            "view_mode": "graph,tree,pivot",
            "views": [
                (self.env.ref("rental.view_rental_analytics_stock_onhand_graph").id, "graph"),
                (self.env.ref("rental.view_rental_analytics_stock_onhand_tree").id, "list"),
                (self.env.ref("rental.view_rental_analytics_stock_onhand_pivot").id, "pivot"),
            ],
            "domain": self._snapshot_domain(as_of, key),
            "context": {
                "analytics_as_of_date": fields.Date.to_string(as_of),
                "search_default_group_product": 1,
            },
        }

    @api.model
    def _cron_cleanup_old_snapshots(self):
        cutoff = fields.Date.context_today(self) - timedelta(
            days=ONHAND_SNAPSHOT_RETENTION_DAYS
        )
        self.search([("as_of_date", "<", cutoff)]).unlink()
        return True
