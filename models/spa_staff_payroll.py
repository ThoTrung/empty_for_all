# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools.safe_eval import safe_eval


class SpaStaffPayroll(models.Model):
    _name = "spa.staff.payroll"
    _description = "Phiếu lương nhân viên Spa"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date_from desc, id desc"

    name = fields.Char(string="Số phiếu", required=True, copy=False, default=lambda self: _("Mới"))
    employee_id = fields.Many2one(
        "hr.employee",
        string="Nhân viên",
        required=True,
        ondelete="restrict",
        tracking=True,
        index=True,
    )
    user_id = fields.Many2one(
        related="employee_id.user_id",
        string="User",
        store=True,
        readonly=True,
    )
    contract_id = fields.Many2one(
        "hr.contract",
        string="Hợp đồng",
        domain="[('employee_id', '=', employee_id), ('state', '=', 'open')]",
        ondelete="set null",
        tracking=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Công ty",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Tiền tệ",
        required=True,
        default=lambda self: self.env.company.currency_id,
    )
    date_from = fields.Date(string="Từ ngày", required=True, tracking=True)
    date_to = fields.Date(string="Đến ngày", required=True, tracking=True)
    state = fields.Selection(
        [
            ("draft", "Nháp"),
            ("done", "Xác nhận"),
            ("cancel", "Hủy"),
        ],
        default="draft",
        tracking=True,
    )

    wage_fixed = fields.Monetary(
        string="Lương cố định (kỳ)",
        currency_field="currency_id",
        help="Thường lấy từ hợp đồng (lương tháng hoặc nhập tay).",
        tracking=True,
    )
    overtime_hourly_rate = fields.Monetary(
        string="Đơn giá làm thêm / giờ",
        currency_field="currency_id",
        help="Lấy từ hợp đồng nếu có.",
    )

    service_line_ids = fields.One2many(
        "spa.staff.payroll.service.line",
        "payroll_id",
        string="Dịch vụ theo buổi",
    )
    overtime_line_ids = fields.One2many(
        "spa.staff.payroll.overtime.line",
        "payroll_id",
        string="Làm thêm giờ",
    )

    amount_service = fields.Monetary(
        string="Cộng dịch vụ",
        currency_field="currency_id",
        compute="_compute_amounts",
        store=True,
    )
    amount_overtime = fields.Monetary(
        string="Cộng làm thêm",
        currency_field="currency_id",
        compute="_compute_amounts",
        store=True,
    )
    amount_bonus = fields.Monetary(
        string="Thưởng",
        currency_field="currency_id",
        tracking=True,
    )
    amount_insurance = fields.Monetary(
        string="Bảo hiểm / khấu trừ BH (NV)",
        currency_field="currency_id",
        tracking=True,
        help="Các khoản đóng BH hoặc khấu trừ theo quy định (nhập tay).",
    )
    amount_other_deduction = fields.Monetary(
        string="Khấu trừ khác",
        currency_field="currency_id",
        tracking=True,
    )
    amount_total_payable = fields.Monetary(
        string="Tổng phải trả",
        currency_field="currency_id",
        compute="_compute_amounts",
        store=True,
    )

    dayoff_ids = fields.One2many(
        "spa.staff.dayoff",
        compute="_compute_dayoff_ids",
        string="Ngày nghỉ trong kỳ",
    )
    dayoff_count = fields.Integer(string="Số dòng nghỉ", compute="_compute_dayoff_ids")

    @api.depends("employee_id", "date_from", "date_to")
    def _compute_dayoff_ids(self):
        Dayoff = self.env["spa.staff.dayoff"].sudo()
        for rec in self:
            if not rec.employee_id or not rec.date_from or not rec.date_to:
                rec.dayoff_ids = False
                rec.dayoff_count = 0
                continue
            days = Dayoff.search([
                ("employee_id", "=", rec.employee_id.id),
                ("date_start", "<=", rec.date_to),
                ("date_end", ">=", rec.date_from),
            ])
            rec.dayoff_ids = days
            rec.dayoff_count = len(days)

    @api.depends(
        "service_line_ids.amount_share",
        "overtime_line_ids.amount_subtotal",
        "wage_fixed",
        "amount_bonus",
        "amount_insurance",
        "amount_other_deduction",
    )
    def _compute_amounts(self):
        for rec in self:
            amt_svc = sum(rec.service_line_ids.mapped("amount_share"))
            amt_ot = sum(rec.overtime_line_ids.mapped("amount_subtotal"))
            rec.amount_service = amt_svc
            rec.amount_overtime = amt_ot
            rec.amount_total_payable = (
                (rec.wage_fixed or 0.0)
                + amt_svc
                + amt_ot
                + (rec.amount_bonus or 0.0)
                - (rec.amount_insurance or 0.0)
                - (rec.amount_other_deduction or 0.0)
            )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name"):
                vals["name"] = self.env["ir.sequence"].next_by_code("spa.staff.payroll") or "PL"
        return super().create(vals_list)

    @api.onchange("employee_id", "date_from", "date_to")
    def _onchange_load_contract(self):
        if not self.employee_id or not self.date_from or not self.date_to:
            return
        contract = self._find_contract()
        if contract:
            self.contract_id = contract
            self.wage_fixed = contract.wage
            self.overtime_hourly_rate = contract.spa_overtime_hourly_rate

    def _find_contract(self):
        self.ensure_one()
        if not self.employee_id:
            return self.env["hr.contract"]
        return self.env["hr.contract"].search(
            [
                ("employee_id", "=", self.employee_id.id),
                ("state", "=", "open"),
                ("date_start", "<=", self.date_to),
                "|",
                ("date_end", "=", False),
                ("date_end", ">=", self.date_from),
            ],
            order="date_start desc",
            limit=1,
        )

    def action_load_contract_values(self):
        for rec in self:
            c = rec._find_contract()
            if c:
                rec.write({
                    "contract_id": c.id,
                    "wage_fixed": c.wage,
                    "overtime_hourly_rate": c.spa_overtime_hourly_rate,
                })

    def action_open_bookings_calendar(self):
        """Mở Đặt lịch dịch vụ (calendar) lọc theo user nhân viên + kỳ phiếu lương."""
        self.ensure_one()
        if not self.user_id:
            raise UserError(_("Nhân viên chưa gắn user — không lọc được đặt lịch."))
        start = fields.Datetime.to_datetime(self.date_from)
        end_exclusive = fields.Datetime.to_datetime(self.date_to) + timedelta(days=1)
        uid = self.user_id.id
        domain = [
            "&",
            ("start_datetime", ">=", start),
            ("start_datetime", "<", end_exclusive),
            "|",
            ("staff_ids", "in", [uid]),
            ("staff_id", "=", uid),
        ]
        action = self.env["ir.actions.actions"]._for_xml_id("booking_calendar.action_spa_service_booking")
        if not isinstance(action, dict):
            action = dict(action)
        action["domain"] = domain
        action["name"] = _("Đặt lịch (theo phiếu lương)")
        base_ctx = action.get("context") or {}
        if isinstance(base_ctx, str):
            base_ctx = safe_eval(base_ctx, {"context": self.env.context})
        merged = dict(base_ctx)
        merged.setdefault("search_default_confirmed", 0)
        merged["initial_date"] = fields.Date.to_string(self.date_from)
        action["context"] = merged
        return action

    def _session_datetime_domain(self):
        self.ensure_one()
        start = fields.Datetime.to_datetime(self.date_from)
        end_exclusive = fields.Datetime.to_datetime(self.date_to) + timedelta(days=1)
        return [
            ("state", "=", "done"),
            ("date", ">=", start),
            ("date", "<", end_exclusive),
        ]

    def _session_participant_users(self, session):
        """res.users recordset for therapists on session."""
        users = session.therapist_ids
        if not users and session.therapist_id:
            users = session.therapist_id
        return users

    def action_recompute_service_lines(self):
        """Tính dòng dịch vụ từ spa.treatment.session (done) trong kỳ."""
        Session = self.env["spa.treatment.session"].sudo()
        for rec in self:
            if rec.state == "done":
                raise UserError(_("Không tính lại khi phiếu đã xác nhận."))
            if not rec.user_id:
                raise UserError(_("Nhân viên chưa gắn user — không thể khớp buổi trị liệu."))
            rec.service_line_ids.unlink()
            domain = rec._session_datetime_domain()
            sessions = Session.search(domain)
            lines = []
            uid = rec.user_id.id
            for session in sessions:
                users = rec._session_participant_users(session)
                if not users:
                    continue
                if uid not in users.ids:
                    continue
                product = session.product_id
                if not product:
                    continue
                tmpl = product.product_tmpl_id
                # Trường có sẵn trong module spa (product.template)
                amount_total = float(tmpl.service_employee_salary or 0.0)
                n = len(users)
                share = (amount_total / n) if n else 0.0
                lines.append({
                    "payroll_id": rec.id,
                    "session_id": session.id,
                    "amount_total": amount_total,
                    "staff_count": n,
                    "amount_share": share,
                })
            if lines:
                self.env["spa.staff.payroll.service.line"].create(lines)
        return True

    def action_recompute_overtime_lines(self):
        """Lấy các đăng ký làm thêm đã duyệt trong kỳ."""
        Overtime = self.env["spa.staff.overtime.request"].sudo()
        for rec in self:
            if rec.state == "done":
                raise UserError(_("Không tính lại khi phiếu đã xác nhận."))
            if not rec.employee_id:
                raise UserError(_("Chưa chọn nhân viên."))
            rec.overtime_line_ids.unlink()
            rate = rec.overtime_hourly_rate or 0.0
            requests = Overtime.search([
                ("employee_id", "=", rec.employee_id.id),
                ("state", "=", "approved"),
                ("overtime_date", ">=", rec.date_from),
                ("overtime_date", "<=", rec.date_to),
            ])
            lines = []
            for req in requests:
                amt = (req.hours or 0.0) * rate
                lines.append({
                    "payroll_id": rec.id,
                    "request_id": req.id,
                    "overtime_date": req.overtime_date,
                    "hours": req.hours,
                    "hourly_rate": rate,
                    "amount_subtotal": amt,
                    "note": req.note or req.name,
                })
            if lines:
                self.env["spa.staff.payroll.overtime.line"].create(lines)
        return True

    def action_confirm(self):
        self.write({"state": "done"})

    def action_draft(self):
        self.write({"state": "draft"})

    def action_cancel(self):
        self.write({"state": "cancel"})
