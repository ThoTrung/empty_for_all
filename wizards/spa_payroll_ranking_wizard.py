# -*- coding: utf-8 -*-

from collections import defaultdict
from calendar import monthrange
from datetime import date, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SpaPayrollRankingComputeWizard(models.TransientModel):
    _name = "spa.payroll.ranking.compute.wizard"
    _description = "Chốt xếp hạng kỳ (tháng/năm)"

    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    period_type = fields.Selection(
        [("month", "Tháng"), ("year", "Năm")],
        required=True,
        default="month",
    )
    year = fields.Integer(required=True, default=lambda self: fields.Date.context_today(self).year)
    month = fields.Integer(default=lambda self: fields.Date.context_today(self).month)

    def action_compute(self):
        self.ensure_one()
        if self.period_type == "month" and not (1 <= int(self.month or 0) <= 12):
            raise UserError(_("Tháng không hợp lệ."))
        Result = self.env["spa.payroll.ranking.result"]
        domain = [
            ("company_id", "=", self.company_id.id),
            ("period_type", "=", self.period_type),
            ("year", "=", self.year),
            ("state", "in", ("draft", "need_review")),
        ]
        if self.period_type == "month":
            domain.append(("month", "=", self.month))
        Result.search(domain).unlink()

        prizes = self.env["spa.payroll.ranking.prize"].search([
            ("active", "=", True),
            ("period_type", "=", self.period_type),
            "|",
            ("company_id", "=", False),
            ("company_id", "=", self.company_id.id),
        ])
        if not prizes:
            raise UserError(_("Chưa cấu hình giải thưởng xếp hạng cho kỳ này."))

        date_from, date_to = self._bounds()
        scores = {
            "sales_revenue": self._scores_sales(date_from, date_to),
            "customer_requested_count": self._scores_requested(date_from, date_to),
            "overtime_hours": self._scores_ot(date_from, date_to),
        }

        created = Result.browse()
        for metric, score_map in scores.items():
            metric_prizes = prizes.filtered(lambda p, m=metric: p.metric == m).sorted("rank")
            if not metric_prizes or not score_map:
                continue
            ranking = sorted(score_map.items(), key=lambda item: (-item[1], item[0]))
            for prize in metric_prizes:
                idx = prize.rank - 1
                if idx < 0 or idx >= len(ranking):
                    continue
                emp_id, score = ranking[idx]
                same = [e for e, s in ranking if abs(s - score) < 1e-6]
                vals = {
                    "company_id": self.company_id.id,
                    "period_type": self.period_type,
                    "year": self.year,
                    "month": self.month if self.period_type == "month" else False,
                    "metric": metric,
                    "rank": prize.rank,
                    "score": score,
                    "amount": prize.amount,
                    "prize_id": prize.id,
                }
                if len(same) > 1:
                    vals.update({
                        "employee_id": False,
                        "state": "need_review",
                        "note": _("Hòa employee_ids=%s — chọn NV trước khi chốt") % (same,),
                    })
                else:
                    vals.update({"employee_id": emp_id, "state": "draft"})
                created |= Result.create(vals)

        return {
            "type": "ir.actions.act_window",
            "name": _("Kết quả xếp hạng"),
            "res_model": "spa.payroll.ranking.result",
            "view_mode": "tree,form",
            "domain": [("id", "in", created.ids)],
            "target": "current",
        }

    def _bounds(self):
        if self.period_type == "year":
            return date(self.year, 1, 1), date(self.year, 12, 31)
        last = monthrange(self.year, self.month)[1]
        return date(self.year, self.month, 1), date(self.year, self.month, last)

    def _eligible_employees(self):
        return self.env["hr.employee"].search([
            ("company_id", "=", self.company_id.id),
            ("user_id", "!=", False),
        ])

    def _scores_sales(self, date_from, date_to):
        """Doanh số xếp hạng: cùng DEC cash-basis (SO settled / HĐ lẻ paid theo ngày đủ tiền)."""
        Payroll = self.env["spa.staff.payroll"]
        scores = {}
        for emp in self._eligible_employees():
            proxy = Payroll.new({
                "company_id": self.company_id.id,
                "date_from": date_from,
                "date_to": date_to,
                "employee_id": emp.id,
            })
            total = proxy._spa_net_invoice_revenue_for_sales_user(emp.user_id)
            if total:
                scores[emp.id] = total
        return scores

    def _scores_requested(self, date_from, date_to):
        Session = self.env["spa.treatment.session"].sudo()
        start = fields.Datetime.to_datetime(date_from)
        end_exclusive = fields.Datetime.to_datetime(date_to) + timedelta(days=1)
        scores = defaultdict(int)
        for emp in self._eligible_employees():
            n = Session.search_count([
                ("state", "=", "done"),
                ("date", ">=", start),
                ("date", "<", end_exclusive),
                ("therapist_ids", "in", [emp.user_id.id]),
                ("spa_payroll_shift_kind", "=", "long"),
                ("spa_payroll_customer_requested", "=", True),
            ])
            if n:
                scores[emp.id] = n
        return dict(scores)

    def _scores_ot(self, date_from, date_to):
        OT = self.env["spa.staff.overtime.request"].sudo()
        scores = defaultdict(float)
        for emp in self._eligible_employees():
            reqs = OT.search([
                ("employee_id", "=", emp.id),
                ("state", "=", "approved"),
                ("overtime_date", ">=", date_from),
                ("overtime_date", "<=", date_to),
            ])
            hours = sum(reqs.mapped("hours"))
            if hours:
                scores[emp.id] = hours
        return dict(scores)


class SpaPayrollLoadDefaultTiersWizard(models.TransientModel):
    _name = "spa.payroll.load.default.tiers.wizard"
    _description = "Nạp bậc lương mặc định (spec)"

    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
    )

    def action_load(self):
        self.ensure_one()
        self.env["spa.payroll.config"]._spa_ensure_default_tiers(self.company_id)
        return {"type": "ir.actions.client", "tag": "display_notification", "params": {
            "title": _("Đã nạp bậc mặc định"),
            "message": _("Bậc ca dài / khách đặt / KPI / giải thưởng tháng đã được đảm bảo (idempotent)."),
            "type": "success",
            "sticky": False,
        }}
