# -*- coding: utf-8 -*-

from odoo import fields, models


class SpaStaffPayrollServiceLine(models.Model):
    _name = "spa.staff.payroll.service.line"
    _description = "Chi tiết dịch vụ trên phiếu lương"
    _order = "session_date desc, id desc"

    payroll_id = fields.Many2one(
        "spa.staff.payroll",
        string="Phiếu lương",
        required=True,
        ondelete="cascade",
        index=True,
    )
    session_id = fields.Many2one(
        "spa.treatment.session",
        string="Buổi trị liệu",
        required=True,
        ondelete="restrict",
        index=True,
    )
    booking_id = fields.Many2one(
        related="session_id.booking_id",
        string="Đặt lịch",
        store=True,
        readonly=True,
    )
    product_id = fields.Many2one(
        related="session_id.product_id",
        string="Dịch vụ / gói",
        store=True,
        readonly=True,
    )
    session_date = fields.Datetime(
        related="session_id.date",
        string="Ngày buổi",
        store=True,
        readonly=True,
    )
    amount_total = fields.Monetary(
        string="Tiền buổi (cấu hình SP)",
        currency_field="currency_id",
        help="Tổng tiền theo sản phẩm trước khi chia.",
    )
    staff_count = fields.Integer(
        string="Số NV",
        help="Số nhân viên tham gia buổi (chia đều).",
    )
    amount_share = fields.Monetary(
        string="Tiền NV này",
        currency_field="currency_id",
        help="Phần của nhân viên trên phiếu lương.",
    )
    currency_id = fields.Many2one(
        related="payroll_id.currency_id",
        store=True,
        readonly=True,
    )


class SpaStaffPayrollOvertimeLine(models.Model):
    _name = "spa.staff.payroll.overtime.line"
    _description = "Chi tiết làm thêm giờ trên phiếu lương"
    _order = "overtime_date desc, id desc"

    payroll_id = fields.Many2one(
        "spa.staff.payroll",
        string="Phiếu lương",
        required=True,
        ondelete="cascade",
        index=True,
    )
    request_id = fields.Many2one(
        "spa.staff.overtime.request",
        string="Đăng ký làm thêm",
        ondelete="set null",
    )
    overtime_date = fields.Date(string="Ngày", required=True)
    hours = fields.Float(string="Giờ", required=True)
    hourly_rate = fields.Monetary(
        string="Đơn giá / giờ",
        currency_field="currency_id",
    )
    amount_subtotal = fields.Monetary(
        string="Thành tiền",
        currency_field="currency_id",
    )
    currency_id = fields.Many2one(
        related="payroll_id.currency_id",
        store=True,
        readonly=True,
    )
    note = fields.Char(string="Ghi chú")
