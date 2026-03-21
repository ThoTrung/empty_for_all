# -*- coding: utf-8 -*-

from calendar import monthrange
from datetime import date

from odoo import fields, models, _
from odoo.exceptions import UserError


class SpaStaffPayrollGenerateWizard(models.TransientModel):
    _name = "spa.staff.payroll.generate.wizard"
    _description = "Tạo phiếu lương theo tháng"

    year = fields.Integer(string="Năm", required=True, default=lambda self: date.today().year)
    month = fields.Integer(string="Tháng", required=True, default=lambda self: date.today().month)
    company_id = fields.Many2one(
        "res.company",
        string="Công ty",
        required=True,
        default=lambda self: self.env.company,
    )
    employee_ids = fields.Many2many(
        "hr.employee",
        string="Nhân viên",
        help="Để trống = tất cả nhân viên có hợp đồng đang chạy trong tháng.",
    )

    def action_generate(self):
        self.ensure_one()
        if not (1 <= self.month <= 12):
            raise UserError(_("Tháng không hợp lệ."))
        last = monthrange(self.year, self.month)[1]
        date_from = date(self.year, self.month, 1)
        date_to = date(self.year, self.month, last)

        Contract = self.env["hr.contract"].sudo()
        domain = [
            ("company_id", "=", self.company_id.id),
            ("state", "=", "open"),
            ("date_start", "<=", date_to),
            "|",
            ("date_end", "=", False),
            ("date_end", ">=", date_from),
        ]
        contracts = Contract.search(domain)
        if self.employee_ids:
            contracts = contracts.filtered(lambda c: c.employee_id in self.employee_ids)
        if not contracts:
            raise UserError(_("Không tìm thấy hợp đồng phù hợp."))

        Payroll = self.env["spa.staff.payroll"]
        created = Payroll
        for contract in contracts:
            emp = contract.employee_id
            if not emp.user_id:
                continue
            existing = Payroll.search(
                [
                    ("employee_id", "=", emp.id),
                    ("date_from", "=", date_from),
                    ("date_to", "=", date_to),
                    ("company_id", "=", self.company_id.id),
                ],
                limit=1,
            )
            if existing:
                created |= existing
                continue
            p = Payroll.create({
                "employee_id": emp.id,
                "company_id": self.company_id.id,
                "date_from": date_from,
                "date_to": date_to,
                "contract_id": contract.id,
                "wage_fixed": contract.wage,
                "overtime_hourly_rate": contract.spa_overtime_hourly_rate,
                "currency_id": contract.currency_id.id,
            })
            p.action_recompute_service_lines()
            p.action_recompute_overtime_lines()
            created |= p

        if not created:
            raise UserError(_("Không tạo được phiếu nào (kiểm tra nhân viên đã gắn user)."))

        return {
            "type": "ir.actions.act_window",
            "name": _("Phiếu lương"),
            "res_model": "spa.staff.payroll",
            "view_mode": "tree,form",
            "domain": [("id", "in", created.ids)],
        }
