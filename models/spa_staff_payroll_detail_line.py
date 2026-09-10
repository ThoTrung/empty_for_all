# -*- coding: utf-8 -*-

from odoo import fields, models


class SpaStaffPayrollCommissionLine(models.Model):
    _name = "spa.staff.payroll.commission.line"
    _description = "Chi tiết hoa hồng SP trên phiếu lương"
    _order = "settle_date, sale_order_id, move_id, id"

    payroll_id = fields.Many2one(
        "spa.staff.payroll",
        string="Phiếu lương",
        required=True,
        ondelete="cascade",
        index=True,
    )
    product_id = fields.Many2one(
        "product.product",
        string="Sản phẩm",
        required=True,
        ondelete="restrict",
    )
    categ_id = fields.Many2one(
        "product.category",
        string="Danh mục",
        ondelete="set null",
    )
    product_branch = fields.Selection(
        [
            ("clinic", "Phòng khám"),
            ("spa", "Spa"),
        ],
        string="Chi nhánh",
        index=True,
        help="Phân loại tại thời điểm tính lương, suy từ 'Chi nhánh sử dụng' của SP. "
        "SP = 'Phòng khám' -> clinic; còn lại (Spa / Cả hai / chưa đặt) -> spa.",
    )
    sale_order_id = fields.Many2one(
        "sale.order",
        string="Đơn hàng",
        ondelete="set null",
        index=True,
    )
    move_id = fields.Many2one(
        "account.move",
        string="Hóa đơn",
        ondelete="set null",
        index=True,
    )
    settle_date = fields.Date(
        string="Ngày",
        help="SO: ngày đơn hoàn thành (settled). Hóa đơn lẻ / hóa đơn trả hàng: "
        "ngày hóa đơn đó được thanh toán đủ.",
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Khách hàng",
        ondelete="set null",
        index=True,
    )
    partner_code = fields.Char(
        string="Mã KH",
        related="partner_id.customer_code",
        store=False,
    )
    quantity = fields.Float(string="Số lượng", digits="Product Unit of Measure")
    price_unit = fields.Float(string="Đơn giá", digits="Product Price")
    discount = fields.Float(string="Chiết khấu (%)", digits="Discount")
    price_subtotal = fields.Monetary(
        string="Thành tiền",
        currency_field="currency_id",
    )
    commission_percent = fields.Float(string="% HH")
    commission_amount = fields.Monetary(
        string="Hoa hồng",
        currency_field="currency_id",
    )
    currency_id = fields.Many2one(
        related="payroll_id.currency_id",
        store=True,
        readonly=True,
    )
    company_id = fields.Many2one(
        related="payroll_id.company_id",
        store=True,
        readonly=True,
    )


class SpaStaffPayrollKpiLine(models.Model):
    _name = "spa.staff.payroll.kpi.line"
    _description = "Chi tiết KPI doanh thu trên phiếu lương"
    _order = "sale_order_id, move_id, id"

    payroll_id = fields.Many2one(
        "spa.staff.payroll",
        string="Phiếu lương",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sale_order_id = fields.Many2one(
        "sale.order",
        string="Đơn hàng",
        ondelete="set null",
        index=True,
    )
    move_id = fields.Many2one(
        "account.move",
        string="Hóa đơn",
        ondelete="set null",
        index=True,
    )
    source_name = fields.Char(string="Nguồn")
    revenue_amount = fields.Monetary(
        string="Doanh thu",
        currency_field="currency_id",
        help="Doanh thu nguồn (SO recognized net CK trừ cọc, hoặc HĐ amount_total_signed).",
    )
    kpi_percent = fields.Float(string="% KPI kỳ")
    kpi_amount = fields.Monetary(
        string="Tiền KPI",
        currency_field="currency_id",
        help="revenue_amount × % KPI kỳ.",
    )
    currency_id = fields.Many2one(
        related="payroll_id.currency_id",
        store=True,
        readonly=True,
    )
    company_id = fields.Many2one(
        related="payroll_id.company_id",
        store=True,
        readonly=True,
    )
