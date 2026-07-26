# -*- coding: utf-8 -*-

from odoo import fields, models


class SpaStaffPayrollCommissionLine(models.Model):
    _name = "spa.staff.payroll.commission.line"
    _description = "Chi tiết hoa hồng SP trên phiếu lương"
    _order = "sale_order_id, move_id, id"

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
        help="Doanh thu nguồn (SO amount_total hoặc HĐ amount_total_signed).",
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
