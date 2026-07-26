# -*- coding: utf-8 -*-

from calendar import monthrange
from datetime import date

from odoo import fields, models, _
from odoo.exceptions import RedirectWarning, UserError


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
            msg = _(
                "Không có hợp đồng lao động phù hợp cho công ty %(company)s và tháng %(month)d/%(year)d.\n\n"
                "Cần hợp đồng trạng thái «Đang chạy» (Running), ngày bắt đầu trước hoặc trong tháng, "
                "ngày kết thúc để trống hoặc sau ngày đầu tháng.\n\n"
                "Spa → Lương NV → «Hợp đồng lao động» để tạo hợp đồng; «Nhân viên (HR)» để gắn user đăng nhập.",
                company=self.company_id.display_name,
                month=self.month,
                year=self.year,
            )
            act = self.env.ref("hr_contract.action_hr_contract", raise_if_not_found=False)
            if act:
                raise RedirectWarning(msg, act.id, _("Mở Hợp đồng"))
            raise UserError(msg)

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
            p_vals = {
                "employee_id": emp.id,
                "company_id": self.company_id.id,
                "date_from": date_from,
                "date_to": date_to,
                "contract_id": contract.id,
                "currency_id": contract.currency_id.id,
            }
            p_vals.update(
                Payroll._spa_prorate_contract_wage(contract, date_from, date_to)
            )
            p_vals["overtime_hourly_rate"] = contract.spa_overtime_hourly_rate
            p = Payroll.create(p_vals)
            # Ledger service_payout_session (1 dòng tổng) + tab Buổi làm = SoT tiền công buổi.
            p.action_recompute_overtime_lines()
            p.action_recompute_payroll_extras()
            created |= p

        if not created:
            msg = _(
                "Có hợp đồng nhưng không tạo được phiếu: nhân viên cần có User (tài khoản đăng nhập) trên hồ sơ HR, "
                "hoặc tháng này đã có phiếu cho từng người.\n\n"
                "Spa → Lương NV → «Nhân viên (HR)»."
            )
            act = self.env.ref("hr.open_view_employee_list_my", raise_if_not_found=False)
            if act:
                raise RedirectWarning(msg, act.id, _("Mở Nhân viên"))
            raise UserError(msg)

        return {
            "type": "ir.actions.act_window",
            "name": _("Phiếu lương"),
            "res_model": "spa.staff.payroll",
            "view_mode": "tree,form",
            "domain": [("id", "in", created.ids)],
        }
