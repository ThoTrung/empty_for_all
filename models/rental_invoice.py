# models/transport.py
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
from datetime import date

_logger = logging.getLogger(__name__)


class RentalInvoice(models.Model):
    _name = "rental.invoice"
    _description = "Hóa đơn thuê"
    _rec_name = "code"

    name = fields.Char(string="Tên")
    code = fields.Char(string="Mã")
    rental_contract_id = fields.Many2one('rental.contract', string="Hợp đồng thuê", ondelete='cascade', index=True)
    company_id = fields.Many2one(
        'res.company',
        related='rental_contract_id.company_id',
        store=True,
        readonly=True,
        index=True,
    )
    start_date = fields.Date(string="Từ ngày")
    end_date = fields.Date(string="Đến ngày")
    state = fields.Selection([
        ('draft', 'Nháp'),
        ('done', 'Hoàn thành'),
        ('cancel', 'Đã hủy'),
    ], string='Trạng thái', default='draft', tracking=True)

    rental_invoice_line_ids = fields.One2many('rental.invoice.line', 'rental_invoice_id', string='Dòng hóa đơn thuê')
    total_price = fields.Float(string='Thành tiền', compute='_compute_total_price')
    currency_id = fields.Many2one(
        'res.currency', required=True,
        default=lambda self: self.env.company.currency_id.id,
    )

    @api.model
    def create(self, vals):
        vals['code'] = self.env['ir.sequence'].next_by_code('rental.invoice')
        return super().create(vals)

    @api.depends('rental_invoice_line_ids', 'rental_invoice_line_ids.total_price')
    def _compute_total_price(self):
        for rec in self:
            total_price = 0
            for line in rec.rental_invoice_line_ids:
                total_price += line.total_price
            rec.write({
                'total_price': total_price
            })
    #
    # @api.model
    # def create(self, vals):
    #     vals['code'] = self.env['ir.sequence'].next_by_code('rr.transport')
    #     return super().create(vals)
    #
    # def action_create_pickings(self):
    #     for rec in self:
    #         if not rec.rental_contract_id:
    #             raise UserError(_("Không có hợp đồng tương ứng."))


class RentalInvoiceLine(models.Model):
    _name = "rental.invoice.line"
    _description = "Dòng hóa đơn thuê"
    _order = "product_tmpl_id, id"

    name = fields.Char(string="Tên")
    rental_invoice_id = fields.Many2one('rental.invoice', string='Hóa đơn thuê')
    company_id = fields.Many2one(
        'res.company',
        related='rental_invoice_id.company_id',
        store=True,
        readonly=True,
        index=True,
    )
    start_date = fields.Date(string='Từ ngày')
    end_date = fields.Date(string='Đến ngày')
    rental_days = fields.Integer(string='Số ngày thuê', compute='_compute_total_price', store=True)
    product_id = fields.Many2one('product.product', string="Sản phẩm", required=True)
    product_tmpl_id = fields.Many2one(
        related='product_id.product_tmpl_id',
        store=True,
        index=True,
    )
    uom_id = fields.Many2one(
        "uom.uom",
        string="ĐVT (mẫu/kho)",
        related="product_id.uom_id",
        store=True,
    )
    staff_display_uom_id = fields.Many2one(
        "uom.uom",
        string="Đơn vị hiển thị",
        compute="_compute_staff_display_uom_id",
        store=True,
        readonly=True,
    )
    qty = fields.Integer(string="Số lượng", default=1)
    unit_price = fields.Float(string='Đơn giá')
    total_price = fields.Float(string='Thành tiền', compute='_compute_total_price', store=True)
    currency_id = fields.Many2one(
        'res.currency',
        related='rental_invoice_id.currency_id',
        store=True,
    )

    @api.depends(
        "product_id",
        "product_id.staff_display_uom_id",
        "product_id.uom_id",
    )
    def _compute_staff_display_uom_id(self):
        for line in self:
            if line.product_id:
                line.staff_display_uom_id = line.product_id._get_staff_display_uom()
            else:
                line.staff_display_uom_id = False

    @api.depends('start_date', 'end_date', 'qty', 'unit_price')
    def _compute_total_price(self):
        for rec in self:
            rental_days = (rec.end_date - rec.start_date).days + 1
            total_price = rental_days * rec.qty * rec.unit_price
            rec.write({
                'rental_days': rental_days,
                'total_price': total_price,
            })

#
# class PriceList(models.Model):
#     _name = "rr.price.list"
#     _description = "Price list"
#
#     start_date = fields.Date(string="Từ ngày")
#     end_date = fields.Date(string="Từ ngày")


# class TransportLine(models.Model):
#     _name = "rr.price.list.line"
#     _description = "Price list line"
#
#     price_list_id = fields.Many2one('rr.price.list', string="Price list", ondelete='cascade', required=True)
#     product_id = fields.Many2one('product.product', string="Sản phẩm", required=True)
#     uom_id = fields.Many2one('uom.uom', string="UoM", related='product_id.uom_id', store=True)
#     qty = fields.Integer(string="Số lượng", default=1)
#     name = fields.Char(string="Description")



# class TransportDriver(models.Model):
#     _name = "rr.transport.driver"
#     _description = "Driver who transport product."
#
#     name = fields.Char(string='Name')
#     driver_name =
#     phone = fields.Char(string='Phone')
#     plate = fields.Char(string='Plate')

