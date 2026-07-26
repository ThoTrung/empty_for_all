# -*- coding: utf-8 -*-

from odoo import api, fields, models


class SpaPayrollTierCompanyMixin(models.AbstractModel):
    """Công ty tùy chọn: để trống = bậc áp dụng mọi công ty."""

    _name = "spa.payroll.tier.company.mixin"
    _description = "Mixin công ty / tiền tệ cho bậc payroll"

    company_id = fields.Many2one(
        "res.company",
        string="Công ty",
        required=False,
        index=True,
        help="Để trống: áp dụng mọi công ty. Có giá trị: chỉ công ty đó; khi tính lương, bậc theo công ty được ưu tiên hơn bậc chung.",
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Tiền tệ",
        required=True,
        default=lambda self: self.env.company.currency_id,
        help="Dùng cho số tiền bậc. Khi chọn công ty, có thể đồng bộ tiền tệ từ công ty.",
    )

    @api.onchange("company_id")
    def _onchange_payroll_tier_company_id(self):
        for rec in self:
            if rec.company_id:
                rec.currency_id = rec.company_id.currency_id


class SpaPayrollConfig(models.Model):
    _name = "spa.payroll.config"
    _description = "Cấu hình payroll Spa (theo công ty)"

    company_id = fields.Many2one(
        "res.company",
        string="Công ty",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    lunch_support_amount = fields.Monetary(
        string="Hỗ trợ ăn trưa (ngày đủ điều kiện)",
        currency_field="currency_id",
        default=0.0,
    )
    lunch_min_minutes = fields.Integer(
        string="Ngưỡng phút/ngày (ăn trưa)",
        default=480,
        help="Tổng duration_minutes buổi done trong ngày phải lớn hơn ngưỡng này. Mặc định 480 (= 8 giờ).",
    )
    currency_id = fields.Many2one(
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )

    _sql_constraints = [
        ("uniq_company", "unique(company_id)", "Chỉ được một bản ghi cấu hình payroll cho mỗi công ty."),
    ]

    @api.model
    def _spa_ensure_default_tiers(self, company=None):
        """Idempotent seed global (company_id trống): long / requested / KPI / prizes.

        ``company`` chỉ dùng để tạo ``spa.payroll.config`` theo công ty hiện tại (lunch).
        """
        company = company or self.env.company
        currency = company.currency_id
        Long = self.env["spa.payroll.long.shift.tier"]
        Req = self.env["spa.payroll.requested.shift.tier"]
        Kpi = self.env["spa.payroll.kpi.revenue.tier"]
        Prize = self.env["spa.payroll.ranking.prize"]

        def ensure_long(name, min_c, max_c, amt):
            domain = [
                ("company_id", "=", False),
                ("min_count", "=", min_c),
                ("amount_per_shift", "=", amt),
            ]
            if max_c:
                domain.append(("max_count", "=", max_c))
            else:
                domain.append(("max_count", "in", [False, 0]))
            if not Long.search(domain, limit=1):
                Long.create({
                    "company_id": False,
                    "currency_id": currency.id,
                    "name": name,
                    "min_count": min_c,
                    "max_count": max_c or False,
                    "amount_per_shift": amt,
                })

        ensure_long("38–47 ca dài", 38, 48, 5000)
        ensure_long("48–57 ca dài", 48, 58, 10000)

        def ensure_req(name, min_c, max_c, amt):
            domain = [
                ("company_id", "=", False),
                ("min_count", "=", min_c),
                ("amount_per_shift", "=", amt),
            ]
            if max_c:
                domain.append(("max_count", "=", max_c))
            else:
                domain.append(("max_count", "in", [False, 0]))
            if not Req.search(domain, limit=1):
                Req.create({
                    "company_id": False,
                    "currency_id": currency.id,
                    "name": name,
                    "min_count": min_c,
                    "max_count": max_c or False,
                    "amount_per_shift": amt,
                })

        ensure_req("Khách đặt < 28", 1, 28, 5000)
        ensure_req("Khách đặt ≥ 28", 28, False, 10000)

        kpi_rows = [
            (50_000_000, 0.2, "KPI từ 50tr"),
            (60_000_000, 0.3, "KPI từ 60tr"),
            (70_000_000, 0.4, "KPI từ 70tr"),
            (80_000_000, 0.5, "KPI từ 80tr"),
            (100_000_000, 0.8, "KPI từ 100tr"),
            (120_000_000, 1.0, "KPI từ 120tr"),
            (150_000_000, 1.1, "KPI từ 150tr"),
            (180_000_000, 1.2, "KPI từ 180tr"),
            (200_000_000, 1.3, "KPI từ 200tr"),
            (250_000_000, 1.4, "KPI từ 250tr"),
            (300_000_000, 1.5, "KPI từ 300tr"),
        ]
        for min_rev, pct, name in kpi_rows:
            if not Kpi.search([
                ("company_id", "=", False),
                ("min_revenue", "=", min_rev),
                ("percent", "=", pct),
            ], limit=1):
                Kpi.create({
                    "company_id": False,
                    "currency_id": currency.id,
                    "name": name,
                    "min_revenue": min_rev,
                    "percent": pct,
                })

        month_prizes = [
            ("Nhất doanh số tháng", "sales_revenue", 1, 1_000_000),
            ("Nhì doanh số tháng", "sales_revenue", 2, 500_000),
            ("Nhất khách đặt tháng", "customer_requested_count", 1, 500_000),
            ("Nhất OT tháng", "overtime_hours", 1, 0),
        ]
        for name, metric, rank, amt in month_prizes:
            if not Prize.search([
                ("company_id", "=", False),
                ("period_type", "=", "month"),
                ("metric", "=", metric),
                ("rank", "=", rank),
            ], limit=1):
                Prize.create({
                    "name": name,
                    "company_id": False,
                    "currency_id": currency.id,
                    "period_type": "month",
                    "metric": metric,
                    "rank": rank,
                    "amount": amt,
                })

        year_prizes = [
            ("Nhất doanh số năm", "sales_revenue", 1, 0),
            ("Nhì doanh số năm", "sales_revenue", 2, 0),
            ("Nhất khách đặt năm", "customer_requested_count", 1, 0),
            ("Nhất OT năm", "overtime_hours", 1, 0),
        ]
        for name, metric, rank, amt in year_prizes:
            if not Prize.search([
                ("company_id", "=", False),
                ("period_type", "=", "year"),
                ("metric", "=", metric),
                ("rank", "=", rank),
            ], limit=1):
                Prize.create({
                    "name": name,
                    "company_id": False,
                    "currency_id": currency.id,
                    "period_type": "year",
                    "metric": metric,
                    "rank": rank,
                    "amount": amt,
                })

        cfg = self.search([("company_id", "=", company.id)], limit=1)
        if not cfg:
            self.create({
                "company_id": company.id,
                "lunch_support_amount": 0.0,
                "lunch_min_minutes": 480,
            })
        return True


class SpaPayrollLongShiftTier(models.Model):
    _name = "spa.payroll.long.shift.tier"
    _inherit = ["spa.payroll.tier.company.mixin"]
    _description = "Bậc thưởng ca dài (theo tổng số ca dài trong kỳ)"
    _order = "sequence, min_count"

    sequence = fields.Integer(default=10)
    name = fields.Char(string="Tên", required=True)
    min_count = fields.Integer(string="Từ X (>=)", required=True)
    max_count = fields.Integer(string="Đến X (<)", required=False)
    amount_per_shift = fields.Monetary(
        string="Thưởng / ca",
        currency_field="currency_id",
        required=True,
    )


class SpaPayrollRequestedShiftTier(models.Model):
    _name = "spa.payroll.requested.shift.tier"
    _inherit = ["spa.payroll.tier.company.mixin"]
    _description = "Bậc thưởng khách chủ động đặt (theo tổng số ca dài được đặt trong kỳ)"
    _order = "sequence, min_count"

    sequence = fields.Integer(default=10)
    name = fields.Char(string="Tên", required=True)
    min_count = fields.Integer(string="Từ X (>=)", required=True)
    max_count = fields.Integer(string="Đến X (<)", required=False)
    amount_per_shift = fields.Monetary(
        string="Thưởng / ca",
        currency_field="currency_id",
        required=True,
    )


class SpaPayrollKpiRevenueTier(models.Model):
    _name = "spa.payroll.kpi.revenue.tier"
    _inherit = ["spa.payroll.tier.company.mixin"]
    _description = "Bậc % KPI doanh thu (invoice paid net)"
    _order = "sequence, min_revenue"

    sequence = fields.Integer(default=10)
    name = fields.Char(string="Tên", required=True)
    min_revenue = fields.Monetary(
        string="Từ doanh thu (>=)",
        currency_field="currency_id",
        required=True,
    )
    percent = fields.Float(string="% KPI", digits="Discount", required=True)
