# -*- coding: utf-8 -*-

from calendar import monthrange
from datetime import date, timedelta

from odoo import _, fields, models
from odoo.exceptions import UserError


class SpaPayrollRankingPrize(models.Model):
    _name = "spa.payroll.ranking.prize"
    _description = "Cấu hình giải thưởng xếp hạng lương Spa"
    _order = "period_type, metric, rank"

    name = fields.Char(string="Tên", required=True)
    company_id = fields.Many2one(
        "res.company",
        string="Công ty",
        index=True,
        help="Trống = mọi công ty.",
    )
    period_type = fields.Selection(
        [("month", "Tháng"), ("year", "Năm")],
        string="Kỳ",
        required=True,
        default="month",
        index=True,
    )
    metric = fields.Selection(
        [
            ("sales_revenue", "Doanh số"),
            ("customer_requested_count", "Khách đặt (ca dài)"),
            ("overtime_hours", "Giờ làm thêm"),
        ],
        string="Chỉ số",
        required=True,
        index=True,
    )
    rank = fields.Integer(string="Hạng", required=True, default=1)
    amount = fields.Monetary(string="Số tiền", currency_field="currency_id", required=True)
    currency_id = fields.Many2one(
        "res.currency",
        string="Tiền tệ",
        required=True,
        default=lambda self: self.env.company.currency_id,
    )
    active = fields.Boolean(default=True)


class SpaPayrollRankingResult(models.Model):
    _name = "spa.payroll.ranking.result"
    _description = "Kết quả xếp hạng lương Spa"
    _order = "year desc, month desc, metric, rank"

    company_id = fields.Many2one(
        "res.company",
        string="Công ty",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    period_type = fields.Selection(
        [("month", "Tháng"), ("year", "Năm")],
        string="Kỳ",
        required=True,
        index=True,
    )
    year = fields.Integer(string="Năm", required=True, index=True)
    month = fields.Integer(string="Tháng", index=True)
    metric = fields.Selection(
        [
            ("sales_revenue", "Doanh số"),
            ("customer_requested_count", "Khách đặt (ca dài)"),
            ("overtime_hours", "Giờ làm thêm"),
        ],
        string="Chỉ số",
        required=True,
        index=True,
    )
    rank = fields.Integer(string="Hạng", required=True)
    employee_id = fields.Many2one("hr.employee", string="Nhân viên", ondelete="cascade")
    score = fields.Float(string="Điểm / giá trị")
    amount = fields.Monetary(string="Thưởng", currency_field="currency_id")
    currency_id = fields.Many2one(
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )
    state = fields.Selection(
        [
            ("draft", "Nháp"),
            ("need_review", "Cần xem lại (hòa)"),
            ("confirmed", "Đã chốt"),
        ],
        default="draft",
        required=True,
        index=True,
    )
    payroll_id = fields.Many2one("spa.staff.payroll", string="Phiếu lương", ondelete="set null")
    prize_id = fields.Many2one("spa.payroll.ranking.prize", string="Giải thưởng", ondelete="set null")
    note = fields.Char(string="Ghi chú")

    def action_confirm(self):
        for rec in self:
            if rec.state == "need_review" and not rec.employee_id:
                raise UserError(_("Kết quả hòa cần chọn nhân viên trước khi chốt."))
            if rec.state not in ("draft", "need_review"):
                continue
            payroll = rec._ensure_target_payroll()
            rec._push_ledger_line(payroll)
            rec.write({"state": "confirmed", "payroll_id": payroll.id})
        return True

    def action_reset_draft(self):
        for rec in self.filtered(lambda r: r.state == "confirmed"):
            if rec.payroll_id and rec.payroll_id.state != "draft":
                raise UserError(_("Không hủy chốt khi phiếu lương không còn Nháp."))
            if rec.payroll_id:
                rec.payroll_id.line_ids.filtered(
                    lambda l: (not l.is_manual)
                    and l.category == "ranking_bonus"
                    and l.source_model == rec._name
                    and l.source_id == rec.id
                ).unlink()
            rec.write({"state": "draft", "payroll_id": False})
        return True

    def _period_bounds(self):
        self.ensure_one()
        if self.period_type == "year":
            return date(self.year, 1, 1), date(self.year, 12, 31)
        last = monthrange(self.year, self.month)[1]
        return date(self.year, self.month, 1), date(self.year, self.month, last)

    def _ensure_target_payroll(self):
        self.ensure_one()
        if not self.employee_id:
            raise UserError(_("Thiếu nhân viên trên kết quả xếp hạng."))
        Payroll = self.env["spa.staff.payroll"]
        date_from, date_to = self._period_bounds()
        existing = Payroll.search([
            ("employee_id", "=", self.employee_id.id),
            ("company_id", "=", self.company_id.id),
            ("date_from", "=", date_from),
            ("date_to", "=", date_to),
        ], limit=1)
        if existing:
            if existing.state != "draft":
                raise UserError(
                    _("Phiếu lương của %s phải ở Nháp để nhận thưởng xếp hạng.")
                    % self.employee_id.name
                )
            return existing

        if self.period_type == "month":
            raise UserError(
                _("Chưa có phiếu lương tháng %(m)s/%(y)s cho %(e)s. Hãy tạo phiếu trước.")
                % {"m": self.month, "y": self.year, "e": self.employee_id.name}
            )

        contract = self.env["hr.contract"].search([
            ("employee_id", "=", self.employee_id.id),
            ("state", "=", "open"),
            ("date_start", "<=", date_to),
            "|", ("date_end", "=", False), ("date_end", ">=", date_from),
        ], order="date_start desc", limit=1)
        return Payroll.create({
            "employee_id": self.employee_id.id,
            "company_id": self.company_id.id,
            "date_from": date_from,
            "date_to": date_to,
            "contract_id": contract.id if contract else False,
            "wage_fixed": 0.0,
            "overtime_hourly_rate": contract.spa_overtime_hourly_rate if contract else 0.0,
            "currency_id": self.company_id.currency_id.id,
            "name": _("TN/%s/%s") % (self.year, self.employee_id.id),
        })

    def _push_ledger_line(self, payroll):
        self.ensure_one()
        Line = self.env["spa.staff.payroll.line"]
        Line.search([
            ("payroll_id", "=", payroll.id),
            ("category", "=", "ranking_bonus"),
            ("source_model", "=", self._name),
            ("source_id", "=", self.id),
        ]).unlink()
        metric_label = dict(self._fields["metric"].selection).get(self.metric, self.metric)
        if self.period_type == "year":
            name = _("[THƯỞNG NĂM %(y)s] %(metric)s hạng %(r)d") % {
                "y": self.year,
                "metric": metric_label,
                "r": self.rank,
            }
            code = "RANK_Y"
        else:
            name = _("Thưởng xếp hạng tháng %(m)s/%(y)s — %(metric)s hạng %(r)d") % {
                "m": self.month,
                "y": self.year,
                "metric": metric_label,
                "r": self.rank,
            }
            code = "RANK_M"
        Line.create({
            "payroll_id": payroll.id,
            "category": "ranking_bonus",
            "code": code,
            "name": name,
            "amount": self.amount,
            "is_manual": False,
            "note": _("Score=%(s)s") % {"s": self.score},
            "source_model": self._name,
            "source_id": self.id,
        })
