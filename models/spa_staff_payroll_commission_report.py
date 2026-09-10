# -*- coding: utf-8 -*-
from odoo import fields, models


class SpaStaffPayrollCommissionReport(models.Model):
    """Thống kê hoa hồng nhân viên — đọc lại spa.staff.payroll.commission.line.

    Grain: 1 dòng = 1 dòng chi tiết hoa hồng đã có sẵn trên phiếu lương
    (không tính toán lại, chỉ join thêm thông tin nhân viên/kỳ/khách hàng để
    group-by/pivot).
    """

    _name = "spa.staff.payroll.commission.report"
    _description = "Thống kê hoa hồng nhân viên"
    _auto = False
    _order = "payroll_date_from desc, id desc"
    _rec_name = "employee_id"

    payroll_id = fields.Many2one("spa.staff.payroll", string="Phiếu lương", readonly=True)
    employee_id = fields.Many2one("hr.employee", string="Nhân viên", readonly=True)
    user_id = fields.Many2one("res.users", string="User", readonly=True)
    payroll_date_from = fields.Date(string="Từ ngày (kỳ lương)", readonly=True)
    payroll_date_to = fields.Date(string="Đến ngày (kỳ lương)", readonly=True)
    payroll_state = fields.Selection(
        [
            ("draft", "Nháp"),
            ("to_approve", "Chờ duyệt"),
            ("done", "Xác nhận"),
            ("cancel", "Hủy"),
        ],
        string="Trạng thái phiếu lương",
        readonly=True,
    )
    product_id = fields.Many2one("product.product", string="Sản phẩm", readonly=True)
    categ_id = fields.Many2one("product.category", string="Danh mục", readonly=True)
    sale_order_id = fields.Many2one("sale.order", string="Đơn hàng", readonly=True)
    move_id = fields.Many2one("account.move", string="Hóa đơn", readonly=True)
    partner_id = fields.Many2one("res.partner", string="Khách hàng", readonly=True)
    quantity = fields.Float(string="Số lượng", readonly=True)
    price_subtotal = fields.Monetary(string="Thành tiền", currency_field="currency_id", readonly=True)
    commission_percent = fields.Float(string="% HH", readonly=True)
    commission_amount = fields.Monetary(string="Hoa hồng", currency_field="currency_id", readonly=True)
    currency_id = fields.Many2one("res.currency", string="Tiền tệ", readonly=True)
    company_id = fields.Many2one("res.company", string="Công ty", readonly=True)

    def action_open_payroll(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.payroll_id.display_name,
            "res_model": "spa.staff.payroll",
            "res_id": self.payroll_id.id,
            "view_mode": "form",
            "target": "current",
        }

    @property
    def _table_query(self):
        return """
            SELECT
                cl.id AS id,
                cl.payroll_id AS payroll_id,
                p.employee_id AS employee_id,
                p.user_id AS user_id,
                p.date_from AS payroll_date_from,
                p.date_to AS payroll_date_to,
                p.state AS payroll_state,
                cl.product_id AS product_id,
                cl.categ_id AS categ_id,
                cl.sale_order_id AS sale_order_id,
                cl.move_id AS move_id,
                COALESCE(so.partner_id, am.partner_id) AS partner_id,
                cl.quantity AS quantity,
                cl.price_subtotal AS price_subtotal,
                cl.commission_percent AS commission_percent,
                cl.commission_amount AS commission_amount,
                cl.currency_id AS currency_id,
                cl.company_id AS company_id
            FROM spa_staff_payroll_commission_line cl
            JOIN spa_staff_payroll p ON p.id = cl.payroll_id
            LEFT JOIN sale_order so ON so.id = cl.sale_order_id
            LEFT JOIN account_move am ON am.id = cl.move_id
            WHERE p.state != 'cancel'
        """
