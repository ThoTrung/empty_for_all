# -*- coding: utf-8 -*-

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    spa_work_start_date = fields.Date(
        string="Ngày bắt đầu làm (Spa)",
        help="Mốc tính thâm niên. Nếu trống, lấy ngày bắt đầu hợp đồng sớm nhất.",
    )
    spa_seniority_years = fields.Integer(
        string="Thâm niên (năm)",
        compute="_compute_spa_seniority",
    )
    spa_seniority_months = fields.Integer(
        string="Thâm niên (tháng dư)",
        compute="_compute_spa_seniority",
    )
    spa_seniority_display = fields.Char(
        string="Thâm niên",
        compute="_compute_spa_seniority",
    )

    def _spa_seniority_start_date(self):
        self.ensure_one()
        if self.spa_work_start_date:
            return self.spa_work_start_date
        contracts = self.contract_ids.sorted("date_start")
        if contracts:
            return contracts[0].date_start
        return False

    def _spa_long_leave_days(self, as_of_date):
        """Tổng ngày nghỉ dài (>= 28 ngày) giao với [start, as_of]."""
        self.ensure_one()
        start = self._spa_seniority_start_date()
        if not start or not as_of_date:
            return 0
        leaves = self.env["spa.staff.dayoff"].search([
            ("employee_id", "=", self.id),
            ("date_start", "<=", as_of_date),
            ("date_end", ">=", start),
        ])
        total = 0
        for leave in leaves:
            d0 = max(leave.date_start, start)
            d1 = min(leave.date_end, as_of_date)
            if d1 < d0:
                continue
            days = (d1 - d0).days + 1
            if days >= 28:
                total += days
        return total

    @api.depends("spa_work_start_date", "contract_ids.date_start")
    def _compute_spa_seniority(self):
        today = fields.Date.context_today(self)
        for emp in self:
            start = emp._spa_seniority_start_date()
            if not start or start > today:
                emp.spa_seniority_years = 0
                emp.spa_seniority_months = 0
                emp.spa_seniority_display = "—"
                continue
            leave_days = emp._spa_long_leave_days(today)
            effective_end = today - relativedelta(days=leave_days)
            if effective_end < start:
                emp.spa_seniority_years = 0
                emp.spa_seniority_months = 0
                emp.spa_seniority_display = _("0 năm")
                continue
            delta = relativedelta(effective_end, start)
            years = max(0, delta.years)
            months = max(0, delta.months)
            emp.spa_seniority_years = years
            emp.spa_seniority_months = months
            if months:
                emp.spa_seniority_display = _("%(y)d năm %(m)d tháng") % {
                    "y": years,
                    "m": months,
                }
            else:
                emp.spa_seniority_display = _("%(y)d năm") % {"y": years}
