# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError


class SpaStaffOvertimeRequest(models.Model):
    _name = "spa.staff.overtime.request"
    _description = "Đăng ký làm thêm giờ"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "overtime_date desc, id desc"

    name = fields.Char(
        string="Mã",
        readonly=True,
        copy=False,
        default=lambda self: _("Mới"),
    )
    employee_id = fields.Many2one(
        "hr.employee",
        string="Nhân viên",
        required=True,
        ondelete="cascade",
        tracking=True,
        index=True,
        default=lambda self: self.env["hr.employee"].search(
            [("user_id", "=", self.env.user.id)], limit=1
        ),
    )
    overtime_date = fields.Date(
        string="Ngày làm thêm",
        required=True,
        tracking=True,
        default=fields.Date.context_today,
    )
    hours = fields.Float(string="Số giờ", required=True, tracking=True)
    note = fields.Text(string="Ghi chú")
    state = fields.Selection(
        [
            ("draft", "Nháp"),
            ("submitted", "Chờ duyệt"),
            ("approved", "Đã duyệt"),
            ("rejected", "Từ chối"),
        ],
        string="Trạng thái",
        default="draft",
        tracking=True,
    )
    approved_by = fields.Many2one("res.users", string="Người duyệt", readonly=True)
    approved_date = fields.Datetime(string="Thời điểm duyệt", readonly=True)
    company_id = fields.Many2one(
        "res.company",
        string="Công ty",
        related="employee_id.company_id",
        store=True,
        readonly=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name"):
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code("spa.staff.overtime.request") or "OT"
                )
        return super().create(vals_list)

    def action_submit(self):
        self.write({"state": "submitted"})

    def action_approve(self):
        if not self.env.user.has_group("hr.group_hr_user"):
            if not self.env.user.has_group("spa.group_spa_manager"):
                raise AccessError(_("Chỉ quản lý hoặc HR mới được duyệt."))
        for rec in self:
            if rec.state != "submitted":
                raise UserError(_("Chỉ duyệt khi đang ở trạng thái Chờ duyệt."))
        self.write({
            "state": "approved",
            "approved_by": self.env.user.id,
            "approved_date": fields.Datetime.now(),
        })

    def action_reject(self):
        if not (
            self.env.user.has_group("hr.group_hr_user")
            or self.env.user.has_group("spa.group_spa_manager")
            or self.env.user.has_group("spa_staff_payroll.group_spa_payroll_manager")
        ):
            raise AccessError(_("Chỉ quản lý hoặc HR mới được từ chối."))
        for rec in self:
            if rec.state != "submitted":
                raise UserError(_("Chỉ từ chối khi đang ở trạng thái Chờ duyệt."))
        self.write({
            "state": "rejected",
            "approved_by": self.env.user.id,
            "approved_date": fields.Datetime.now(),
        })

    def action_reset_draft(self):
        self.write({
            "state": "draft",
            "approved_by": False,
            "approved_date": False,
        })
