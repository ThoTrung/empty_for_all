# -*- coding: utf-8 -*-

from datetime import timedelta
from collections import defaultdict

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
            ("to_approve", "Chờ duyệt"),
            ("done", "Xác nhận"),
            ("cancel", "Hủy"),
        ],
        default="draft",
        tracking=True,
    )

    wage_fixed = fields.Monetary(
        string="Lương cố định (kỳ)",
        currency_field="currency_id",
        help="Lấy từ hợp đồng, đã chia theo số ngày hiệu lực HĐ trong kỳ phiếu.",
        tracking=True,
    )
    wage_period_start = fields.Date(
        string="Lương từ ngày",
        readonly=True,
        help="Ngày bắt đầu tính lương cứng (max của đầu kỳ và ngày bắt đầu HĐ).",
    )
    wage_period_end = fields.Date(
        string="Lương đến ngày",
        readonly=True,
        help="Ngày kết thúc tính lương cứng (min của cuối kỳ và ngày kết thúc HĐ).",
    )
    wage_days = fields.Integer(
        string="Số ngày tính lương",
        readonly=True,
        help="Số ngày HĐ giao với kỳ phiếu.",
    )
    wage_days_period = fields.Integer(
        string="Số ngày kỳ",
        readonly=True,
        help="Số ngày trong kỳ phiếu (thường cả tháng).",
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
    line_ids = fields.One2many(
        "spa.staff.payroll.line",
        "payroll_id",
        string="Các khoản lương khác",
    )
    commission_line_ids = fields.One2many(
        "spa.staff.payroll.commission.line",
        "payroll_id",
        string="Chi tiết hoa hồng SP",
    )
    kpi_line_ids = fields.One2many(
        "spa.staff.payroll.kpi.line",
        "payroll_id",
        string="Chi tiết KPI",
    )

    amount_payroll_lines = fields.Monetary(
        string="Cộng các khoản (phiếu)",
        currency_field="currency_id",
        compute="_compute_amounts",
        store=True,
        help="Tổng các dòng ledger trên tab «Lương» (điều chỉnh âm nhập dạng số âm).",
    )

    amount_service = fields.Monetary(
        string="Cộng dịch vụ (tham khảo)",
        currency_field="currency_id",
        compute="_compute_amounts",
        store=True,
        help="Tab Dịch vụ legacy — chỉ tham khảo. Tổng phải trả dùng tiền công buổi trên ledger "
        "(service_payout_session), không cộng amount_service.",
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
    kpi_revenue_base = fields.Monetary(
        string="Doanh thu KPI cơ sở",
        currency_field="currency_id",
        readonly=True,
        help="Doanh thu KPI: SO settled (residual=0) + HĐ không SO đã paid; "
        "kỳ theo ngày đủ tiền — cập nhật khi Tính các khoản.",
    )
    spa_seniority_display = fields.Char(
        related="employee_id.spa_seniority_display",
        string="Thâm niên",
        readonly=True,
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

    @api.model
    def _spa_prorate_contract_wage(self, contract, date_from, date_to):
        """Return wage audit vals: prorated wage_fixed + period day fields.

        wage_fixed = contract.wage × days_worked / days_in_period (calendar days).
        """
        empty = {
            "wage_fixed": 0.0,
            "wage_period_start": False,
            "wage_period_end": False,
            "wage_days": 0,
            "wage_days_period": 0,
        }
        if not contract or not date_from or not date_to:
            return empty
        date_from = fields.Date.to_date(date_from)
        date_to = fields.Date.to_date(date_to)
        if date_to < date_from:
            return empty
        days_period = (date_to - date_from).days + 1
        c_start = fields.Date.to_date(contract.date_start) if contract.date_start else date_from
        c_end = fields.Date.to_date(contract.date_end) if contract.date_end else date_to
        wage_start = max(date_from, c_start)
        wage_end = min(date_to, c_end)
        if wage_end < wage_start:
            return {
                "wage_fixed": 0.0,
                "wage_period_start": False,
                "wage_period_end": False,
                "wage_days": 0,
                "wage_days_period": days_period,
            }
        days_worked = (wage_end - wage_start).days + 1
        wage = float(contract.wage or 0.0) * (float(days_worked) / float(days_period))
        return {
            "wage_fixed": wage,
            "wage_period_start": wage_start,
            "wage_period_end": wage_end,
            "wage_days": days_worked,
            "wage_days_period": days_period,
        }

    def _spa_apply_contract_wage_vals(self, contract):
        """Build write/create vals for wage from contract + current period."""
        self.ensure_one()
        vals = self._spa_prorate_contract_wage(contract, self.date_from, self.date_to)
        vals["overtime_hourly_rate"] = contract.spa_overtime_hourly_rate if contract else 0.0
        return vals

    @api.depends(
        "service_line_ids.amount_share",
        "overtime_line_ids.amount_subtotal",
        "line_ids.amount",
        "line_ids.category",
        "wage_fixed",
        "amount_bonus",
        "amount_insurance",
        "amount_other_deduction",
    )
    def _compute_amounts(self):
        """Tổng phải trả: ledger (gồm service_payout_session) là SoT tiền công buổi.

        ``amount_service`` (tab Dịch vụ legacy) chỉ tham khảo — không cộng vào tổng
        để tránh double-count với ``service_payout_session``.
        """
        for rec in self:
            amt_svc = sum(rec.service_line_ids.mapped("amount_share"))
            amt_ot = sum(rec.overtime_line_ids.mapped("amount_subtotal"))
            amt_extra = sum(rec.line_ids.mapped("amount"))
            rec.amount_service = amt_svc
            rec.amount_overtime = amt_ot
            rec.amount_payroll_lines = amt_extra
            rec.amount_total_payable = (
                (rec.wage_fixed or 0.0)
                + amt_ot
                + amt_extra
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

    @api.onchange("employee_id", "date_from", "date_to", "contract_id")
    def _onchange_load_contract(self):
        if not self.employee_id or not self.date_from or not self.date_to:
            return
        contract = self.contract_id or self._find_contract()
        if contract:
            self.contract_id = contract
            wage_vals = self._spa_prorate_contract_wage(
                contract, self.date_from, self.date_to
            )
            self.wage_fixed = wage_vals["wage_fixed"]
            self.wage_period_start = wage_vals["wage_period_start"]
            self.wage_period_end = wage_vals["wage_period_end"]
            self.wage_days = wage_vals["wage_days"]
            self.wage_days_period = wage_vals["wage_days_period"]
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
                vals = rec._spa_apply_contract_wage_vals(c)
                vals["contract_id"] = c.id
                rec.write(vals)

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
            if rec.state != "draft":
                raise UserError(_("Chỉ tính lại khi phiếu ở trạng thái Nháp."))
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
            if rec.state != "draft":
                raise UserError(_("Chỉ tính lại khi phiếu ở trạng thái Nháp."))
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

    # --- Payroll extras (Solution 1): generic lines + booking-based payouts/bonuses/KPI ---

    def _spa_get_payroll_config(self):
        self.ensure_one()
        cfg = self.env["spa.payroll.config"].sudo().search([("company_id", "=", self.company_id.id)], limit=1)
        return cfg

    def _spa_clear_auto_payroll_lines(self):
        Line = self.env["spa.staff.payroll.line"].sudo()
        for rec in self:
            Line.search([("payroll_id", "=", rec.id), ("is_manual", "=", False)]).unlink()

    def _spa_pick_tier_amount_per_unit(self, tiers, total_units):
        """Pick Monetary rate per unit from tier rows matching total_units."""
        self.ensure_one()
        if total_units is None:
            return 0.0
        tiers = tiers.filtered(
            lambda t: not t.company_id or t.company_id.id == self.company_id.id
        ).sorted(
            # Bậc theo công ty trước bậc chung (cùng khoảng thì lấy theo công ty).
            lambda t: (0 if t.company_id else 1, t.sequence, t.min_count, t.id)
        )
        x = int(total_units)
        for t in tiers:
            if x < int(t.min_count or 0):
                continue
            if t.max_count and x >= int(t.max_count):
                continue
            return float(t.amount_per_shift or 0.0)
        return 0.0

    def _spa_pick_kpi_percent(self, tiers, revenue):
        self.ensure_one()
        tiers = tiers.filtered(
            lambda t: not t.company_id or t.company_id.id == self.company_id.id
        ).sorted(
            # Cùng ngưỡng doanh thu: bậc theo công ty xử lý sau để ghi đè % KPI của bậc chung.
            lambda t: (t.min_revenue, 0 if not t.company_id else 1, t.sequence, t.id)
        )
        rev = float(revenue or 0.0)
        chosen = 0.0
        for t in tiers:
            if rev >= float(t.min_revenue or 0.0):
                chosen = float(t.percent or 0.0)
        return chosen

    def _spa_invoice_linked_sale_orders(self, move):
        """Sale orders linked to this invoice (via invoice lines)."""
        return move.line_ids.sale_line_ids.order_id

    def _spa_invoice_fully_paid_date(self, move):
        """Date when a posted customer invoice became fully paid (residual ≈ 0).

        Prefer last reconciled payment / AML date; fallback to invoice_date.
        """
        self.ensure_one()
        if move.state != "posted":
            return False
        if move.move_type not in ("out_invoice", "out_refund", "out_receipt"):
            return False
        currency = move.currency_id or move.company_id.currency_id
        residual_ok = currency.is_zero(move.amount_residual) or move.payment_state in (
            "paid",
            "in_payment",
            "reversed",
        )
        if not residual_ok:
            return False
        payments = move._get_reconciled_payments()
        if payments:
            return max(fields.Date.to_date(d) for d in payments.mapped("date") if d)
        amls = move._get_reconciled_amls()
        if amls:
            dates = [fields.Date.to_date(d) for d in amls.mapped("date") if d]
            if dates:
                return max(dates)
        return fields.Date.to_date(move.invoice_date or move.date)

    def _spa_is_sale_order_settled(self, order):
        """SO settled: confirmed, fully invoiced, all posted invoices residual ≈ 0."""
        if order.state not in ("sale", "done"):
            return False
        currency = order.currency_id or order.company_id.currency_id
        if not currency.is_zero(float(order.amount_to_invoice or 0.0)):
            return False
        invoices = order.invoice_ids.filtered(
            lambda m: m.state == "posted"
            and m.move_type in ("out_invoice", "out_refund", "out_receipt")
        )
        if not invoices:
            return False
        for inv in invoices:
            if not currency.is_zero(float(inv.amount_residual or 0.0)):
                # Allow payment_state paid when residual not synced (edge / test)
                if inv.payment_state not in ("paid", "in_payment", "reversed"):
                    return False
        return True

    def _spa_sale_order_settled_date(self, order):
        """Date SO became settled = max fully-paid date of its posted invoices."""
        if not self._spa_is_sale_order_settled(order):
            return False
        dates = []
        for inv in order.invoice_ids.filtered(
            lambda m: m.state == "posted"
            and m.move_type in ("out_invoice", "out_refund", "out_receipt")
        ):
            paid_date = self._spa_invoice_fully_paid_date(inv)
            if paid_date:
                dates.append(paid_date)
        return max(dates) if dates else False

    def _spa_sale_orders_settled_in_period(self, user):
        """Confirmed SOs of salesperson that became settled within payroll period."""
        self.ensure_one()
        start = fields.Date.to_date(self.date_from)
        end = fields.Date.to_date(self.date_to)
        Order = self.env["sale.order"].sudo()
        candidates = Order.search([
            ("company_id", "=", self.company_id.id),
            ("user_id", "=", user.id),
            ("state", "in", ("sale", "done")),
        ])
        settled = Order.browse()
        for order in candidates:
            settled_date = self._spa_sale_order_settled_date(order)
            if settled_date and start <= settled_date <= end:
                settled |= order
        return settled

    def _spa_standalone_paid_invoices_in_period(self, user, include_refunds=True):
        """Paid invoices with no SO link; fully-paid date in payroll period."""
        self.ensure_one()
        Move = self.env["account.move"].sudo()
        start = fields.Date.to_date(self.date_from)
        end = fields.Date.to_date(self.date_to)
        move_types = ("out_invoice", "out_refund") if include_refunds else ("out_invoice",)
        moves = Move.search([
            ("company_id", "=", self.company_id.id),
            ("move_type", "in", move_types),
            ("state", "=", "posted"),
            ("invoice_user_id", "=", user.id),
        ])
        result = Move.browse()
        for move in moves:
            if self._spa_invoice_linked_sale_orders(move):
                continue
            paid_date = self._spa_invoice_fully_paid_date(move)
            if paid_date and start <= paid_date <= end:
                result |= move
        return result

    def _spa_commission_detail_vals_for_sale_order(self, order):
        """Detail rows for SO product lines with category commission % > 0."""
        self.ensure_one()
        rows = []
        for line in order.order_line:
            if line.display_type or not line.product_id:
                continue
            if getattr(line, "is_downpayment", False):
                continue
            tmpl = line.product_id.product_tmpl_id
            pct = float(tmpl._spa_get_sales_commission_percent() or 0.0)
            if not pct:
                continue
            subtotal = float(line.price_subtotal or 0.0)
            rows.append({
                "payroll_id": self.id,
                "product_id": line.product_id.id,
                "categ_id": tmpl.categ_id.id if tmpl.categ_id else False,
                "sale_order_id": order.id,
                "move_id": False,
                "quantity": float(line.product_uom_qty or 0.0),
                "price_unit": float(line.price_unit or 0.0),
                "discount": float(line.discount or 0.0),
                "price_subtotal": subtotal,
                "commission_percent": pct,
                "commission_amount": subtotal * (pct / 100.0),
            })
        return rows

    def _spa_commission_detail_vals_for_invoice(self, move):
        """Detail rows for standalone invoice product lines with commission % > 0."""
        self.ensure_one()
        rows = []
        for line in move.invoice_line_ids.filtered(lambda l: l.display_type == "product"):
            if not line.product_id:
                continue
            tmpl = line.product_id.product_tmpl_id
            pct = float(tmpl._spa_get_sales_commission_percent() or 0.0)
            if not pct:
                continue
            subtotal = float(line.price_subtotal or 0.0)
            rows.append({
                "payroll_id": self.id,
                "product_id": line.product_id.id,
                "categ_id": tmpl.categ_id.id if tmpl.categ_id else False,
                "sale_order_id": False,
                "move_id": move.id,
                "quantity": float(line.quantity or 0.0),
                "price_unit": float(line.price_unit or 0.0),
                "discount": float(line.discount or 0.0),
                "price_subtotal": subtotal,
                "commission_percent": pct,
                "commission_amount": subtotal * (pct / 100.0),
            })
        return rows

    def _spa_commission_amount_for_sale_order(self, order):
        """Sum (line price_subtotal × category %) for non-section product SO lines."""
        return sum(
            r["commission_amount"]
            for r in self._spa_commission_detail_vals_for_sale_order(order)
        )

    def _spa_commission_amount_for_invoice(self, move):
        """Sum (invoice line price_subtotal × category %) for product lines."""
        return sum(
            r["commission_amount"]
            for r in self._spa_commission_detail_vals_for_invoice(move)
        )

    def _spa_net_invoice_revenue_for_sales_user(self, user):
        """Cash-basis net revenue: settled SOs in period + standalone paid invoices/refunds."""
        self.ensure_one()
        net = 0.0
        for order in self._spa_sale_orders_settled_in_period(user):
            net += float(order.amount_total or 0.0)
        for move in self._spa_standalone_paid_invoices_in_period(user, include_refunds=True):
            net += float(move.amount_total_signed or 0.0)
        return net

    def _spa_booking_domain_in_period(self):
        self.ensure_one()
        start = fields.Datetime.to_datetime(self.date_from)
        end_exclusive = fields.Datetime.to_datetime(self.date_to) + timedelta(days=1)
        return [
            ("state", "=", "done"),
            ("start_datetime", ">=", start),
            ("start_datetime", "<", end_exclusive),
        ]

    def _spa_price_per_session(self, tmpl):
        self.ensure_one()
        sessions = float(tmpl.spa_sessions_per_unit or 0.0)
        if sessions > 0:
            return float(tmpl.list_price or 0.0) / sessions
        return float(tmpl.list_price or 0.0)

    def _spa_compute_session_service_payout_lines(self):
        """Rebuild buổi làm detail + one aggregated ledger service_payout_session line."""
        Session = self.env["spa.treatment.session"].sudo()
        Line = self.env["spa.staff.payroll.line"].sudo()
        ServiceLine = self.env["spa.staff.payroll.service.line"].sudo()
        for rec in self:
            if rec.state != "draft":
                raise UserError(_("Chỉ tính lại khi phiếu ở trạng thái Nháp."))
            if not rec.user_id:
                raise UserError(_("Nhân viên chưa gắn user — không thể khớp buổi làm."))

            rec.line_ids.filtered(
                lambda l: (not l.is_manual) and l.category == "service_payout_session"
            ).unlink()
            rec.service_line_ids.unlink()

            uid = rec.user_id.id
            start = fields.Datetime.to_datetime(rec.date_from)
            end_exclusive = fields.Datetime.to_datetime(rec.date_to) + timedelta(days=1)
            sessions = Session.search([
                ("state", "=", "done"),
                ("date", ">=", start),
                ("date", "<", end_exclusive),
                ("therapist_ids", "in", [uid]),
            ])

            detail_rows = []
            total_share = 0.0
            for ses in sessions:
                product = ses.product_id
                if not product:
                    continue
                tmpl = product.product_tmpl_id
                staff_lvl = rec.user_id.spa_staff_level_id
                payout_rule = False
                if tmpl.spa_payroll_profile_id:
                    payout_rule = tmpl.spa_payroll_profile_id.payout_line_ids.filtered(
                        lambda r: r.staff_level_id == staff_lvl
                    )[:1]

                if payout_rule:
                    fixed = float(payout_rule.amount_fixed or 0.0)
                    pct = float(payout_rule.percent or 0.0)
                    base = rec._spa_price_per_session(tmpl)
                    amt_full = fixed + (base * pct / 100.0)
                else:
                    amt_full = float(tmpl.service_employee_salary or 0.0)

                # DEC: chia đều cho mọi therapist trên buổi (công bằng multi-therapist).
                therapists = rec._session_participant_users(ses)
                n = len(therapists) or 1
                amt = amt_full / float(n)
                total_share += amt

                detail_rows.append({
                    "payroll_id": rec.id,
                    "session_id": ses.id,
                    "amount_total": amt_full,
                    "staff_count": n,
                    "amount_share": amt,
                })

            if detail_rows:
                ServiceLine.create(detail_rows)
                Line.create({
                    "payroll_id": rec.id,
                    "category": "service_payout_session",
                    "code": "SVC_SES",
                    "name": _("Tiền công buổi (%(n)d buổi)") % {"n": len(detail_rows)},
                    "amount": total_share,
                    "is_manual": False,
                    "note": _(
                        "Tổng phần NV trên %(n)d buổi. Chi tiết tab «Buổi làm»."
                    ) % {"n": len(detail_rows)},
                })

    def _spa_recompute_long_shift_and_requested_bonuses(self):
        TierLong = self.env["spa.payroll.long.shift.tier"].sudo()
        TierReq = self.env["spa.payroll.requested.shift.tier"].sudo()
        Line = self.env["spa.staff.payroll.line"].sudo()
        Session = self.env["spa.treatment.session"].sudo()

        for rec in self:
            if rec.state != "draft":
                raise UserError(_("Chỉ tính lại khi phiếu ở trạng thái Nháp."))
            if not rec.user_id:
                raise UserError(_("Nhân viên chưa gắn user — không thể khớp buổi làm."))

            rec.line_ids.filtered(
                lambda l: (not l.is_manual) and l.category in ("long_shift_bonus", "requested_bonus")
            ).unlink()

            uid = rec.user_id.id
            start = fields.Datetime.to_datetime(rec.date_from)
            end_exclusive = fields.Datetime.to_datetime(rec.date_to) + timedelta(days=1)
            ses_domain = [
                ("state", "=", "done"),
                ("date", ">=", start),
                ("date", "<", end_exclusive),
                ("therapist_ids", "in", [uid]),
            ]
            long_sessions = Session.search(ses_domain + [("spa_payroll_shift_kind", "=", "long")])
            long_count = len(long_sessions)
            req_count = len(long_sessions.filtered(lambda s: s.spa_payroll_customer_requested))

            tiers_long = TierLong.search([
                "|", ("company_id", "=", False),
                ("company_id", "=", rec.company_id.id),
            ])
            rate_long = rec._spa_pick_tier_amount_per_unit(tiers_long, long_count)
            amt_long = rate_long * float(long_count)

            tiers_req = TierReq.search([
                "|", ("company_id", "=", False),
                ("company_id", "=", rec.company_id.id),
            ])
            rate_req = rec._spa_pick_tier_amount_per_unit(tiers_req, req_count)
            amt_req = rate_req * float(req_count)

            rows = []
            if long_count:
                rows.append({
                    "payroll_id": rec.id,
                    "category": "long_shift_bonus",
                    "code": "LONG_SHIFT",
                    "name": _("Thưởng ca dài (tổng %(n)d ca)") % {"n": long_count},
                    "amount": amt_long,
                    "is_manual": False,
                    "note": _("Rate %(rate).0f / ca × %(n)d") % {"rate": rate_long, "n": long_count},
                })
            if req_count:
                rows.append({
                    "payroll_id": rec.id,
                    "category": "requested_bonus",
                    "code": "REQ_STAFF",
                    "name": _("Thưởng khách chủ động đặt (ca dài, %(n)d ca)") % {"n": req_count},
                    "amount": amt_req,
                    "is_manual": False,
                    "note": _("Rate %(rate).0f / ca × %(n)d") % {"rate": rate_req, "n": req_count},
                })
            if rows:
                Line.create(rows)

    def _spa_recompute_kpi_and_sales_commission_lines(self):
        KpiTier = self.env["spa.payroll.kpi.revenue.tier"].sudo()
        Line = self.env["spa.staff.payroll.line"].sudo()
        CommLine = self.env["spa.staff.payroll.commission.line"].sudo()
        KpiLine = self.env["spa.staff.payroll.kpi.line"].sudo()
        for rec in self:
            if rec.state != "draft":
                raise UserError(_("Chỉ tính lại khi phiếu ở trạng thái Nháp."))
            if not rec.user_id:
                raise UserError(_("Nhân viên chưa gắn user — không thể khớp KPI/hoa hồng."))

            rec.line_ids.filtered(
                lambda l: (not l.is_manual) and l.category in ("kpi_revenue", "sales_commission")
            ).unlink()
            rec.commission_line_ids.unlink()
            rec.kpi_line_ids.unlink()

            orders = rec._spa_sale_orders_settled_in_period(rec.user_id)
            standalone_inv = rec._spa_standalone_paid_invoices_in_period(
                rec.user_id, include_refunds=False
            )
            standalone_kpi_inv = rec._spa_standalone_paid_invoices_in_period(
                rec.user_id, include_refunds=True
            )

            net_rev = 0.0
            for order in orders:
                net_rev += float(order.amount_total or 0.0)
            for move in standalone_kpi_inv:
                net_rev += float(move.amount_total_signed or 0.0)

            rec.kpi_revenue_base = net_rev
            tiers = KpiTier.search([
                "|", ("company_id", "=", False),
                ("company_id", "=", rec.company_id.id),
            ])
            kpi_pct = rec._spa_pick_kpi_percent(tiers, net_rev)
            kpi_amt = net_rev * (kpi_pct / 100.0) if kpi_pct else 0.0

            kpi_detail = []
            for order in orders:
                rev = float(order.amount_total or 0.0)
                kpi_detail.append({
                    "payroll_id": rec.id,
                    "sale_order_id": order.id,
                    "move_id": False,
                    "source_name": order.display_name,
                    "revenue_amount": rev,
                    "kpi_percent": kpi_pct,
                    "kpi_amount": rev * (kpi_pct / 100.0) if kpi_pct else 0.0,
                })
            for move in standalone_kpi_inv:
                rev = float(move.amount_total_signed or 0.0)
                kpi_detail.append({
                    "payroll_id": rec.id,
                    "sale_order_id": False,
                    "move_id": move.id,
                    "source_name": move.display_name,
                    "revenue_amount": rev,
                    "kpi_percent": kpi_pct,
                    "kpi_amount": rev * (kpi_pct / 100.0) if kpi_pct else 0.0,
                })
            if kpi_detail:
                KpiLine.create(kpi_detail)

            rows = []
            if kpi_amt:
                rows.append({
                    "payroll_id": rec.id,
                    "category": "kpi_revenue",
                    "code": "KPI_REV",
                    "name": _("KPI doanh thu (net settled %(rev).0f × %(pct).2f%%)")
                    % {"rev": net_rev, "pct": kpi_pct},
                    "amount": kpi_amt,
                    "is_manual": False,
                    "note": _(
                        "SO settled (residual=0) hoặc HĐ không SO đã paid; "
                        "kỳ theo ngày đủ tiền. Chi tiết tab «KPI»."
                    ),
                })

            # Sales commission: settled SOs in period + standalone paid invoices
            comm_detail = []
            for order in orders:
                comm_detail.extend(rec._spa_commission_detail_vals_for_sale_order(order))
            for inv in standalone_inv:
                comm_detail.extend(rec._spa_commission_detail_vals_for_invoice(inv))
            if comm_detail:
                CommLine.create(comm_detail)
            comm_total = sum(r["commission_amount"] for r in comm_detail)

            if comm_total:
                rows.append({
                    "payroll_id": rec.id,
                    "category": "sales_commission",
                    "code": "SALES_COMM",
                    "name": _("Thưởng bán hàng theo danh mục SP"),
                    "amount": comm_total,
                    "is_manual": False,
                    "note": _(
                        "SO thu đủ / HĐ lẻ paid; base = price_subtotal sau CK dòng. "
                        "Chi tiết tab «Hoa hồng SP»."
                    ),
                })

            if rows:
                Line.create(rows)

    def _spa_recompute_lunch_support_lines(self):
        cfg = self.env["spa.payroll.config"].sudo()
        Session = self.env["spa.treatment.session"].sudo()
        Line = self.env["spa.staff.payroll.line"].sudo()

        for rec in self:
            if rec.state != "draft":
                raise UserError(_("Chỉ tính lại khi phiếu ở trạng thái Nháp."))
            if not rec.user_id:
                raise UserError(_("Nhân viên chưa gắn user — không thể khớp buổi làm."))

            rec.line_ids.filtered(lambda l: (not l.is_manual) and l.category == "lunch_support").unlink()

            pay_cfg = rec._spa_get_payroll_config()
            amt_day = float(pay_cfg.lunch_support_amount or 0.0) if pay_cfg else 0.0
            if amt_day <= 0:
                continue
            min_minutes = int(pay_cfg.lunch_min_minutes or 480) if pay_cfg else 480

            uid = rec.user_id.id
            start = fields.Datetime.to_datetime(rec.date_from)
            end_exclusive = fields.Datetime.to_datetime(rec.date_to) + timedelta(days=1)

            minutes_by_day = defaultdict(int)

            sessions = Session.search([
                ("state", "=", "done"),
                ("date", ">=", start),
                ("date", "<", end_exclusive),
                ("therapist_ids", "in", [uid]),
            ])
            for ses in sessions:
                if not ses.date:
                    continue
                day = fields.Datetime.context_timestamp(rec, ses.date).date()
                minutes_by_day[day] += int(ses.duration_minutes or 0)

            eligible_days = [d for d, m in minutes_by_day.items() if m > min_minutes]
            if not eligible_days:
                continue

            Line.create({
                "payroll_id": rec.id,
                "category": "lunch_support",
                "code": "LUNCH",
                "name": _("Hỗ trợ ăn trưa (%(n)d ngày, >%(m)d phút)")
                % {"n": len(eligible_days), "m": min_minutes},
                "amount": amt_day * len(eligible_days),
                "is_manual": False,
                "note": _("Ngày đủ điều kiện: %(days)s") % {"days": ", ".join(str(d) for d in sorted(eligible_days))},
            })

    def action_recompute_payroll_extras(self):
        """Tính các khoản payroll mới: buổi làm + thưởng ca dài + KPI + commission + ăn trưa."""
        for rec in self:
            if rec.state != "draft":
                raise UserError(_("Chỉ tính lại khi phiếu ở trạng thái Nháp."))
            rec._spa_compute_session_service_payout_lines()
            rec._spa_recompute_long_shift_and_requested_bonuses()
            rec._spa_recompute_kpi_and_sales_commission_lines()
            rec._spa_recompute_lunch_support_lines()
        return True

    def action_submit_approve(self):
        for rec in self:
            if rec.state != "draft":
                raise UserError(_("Chỉ gửi duyệt từ trạng thái Nháp."))
            rec.write({"state": "to_approve"})
            rec.activity_schedule(
                "mail.mail_activity_data_todo",
                summary=_("Duyệt phiếu lương %s") % rec.name,
                note=_("Phiếu lương chờ xác nhận."),
                user_id=rec.env.user.id,
            )
        return True

    def action_confirm(self):
        for rec in self:
            if rec.state not in ("draft", "to_approve"):
                raise UserError(_("Không xác nhận được phiếu ở trạng thái hiện tại."))
            rec.write({"state": "done"})
        return True

    def action_draft(self):
        self.write({"state": "draft"})

    def action_cancel(self):
        self.write({"state": "cancel"})
