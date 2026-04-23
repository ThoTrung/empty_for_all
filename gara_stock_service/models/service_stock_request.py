# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class GaraServiceStockRequest(models.Model):
    _name = 'gara.service.stock.request'
    _description = 'Gara Service Stock Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(
        required=True,
        copy=False,
        readonly=True,
        default='New',
        index='trigram',
    )
    company_id = fields.Many2one(
        'res.company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    case_id = fields.Many2one(
        'gara.workshop.case',
        string='Workshop Case',
        required=True,
        tracking=True,
        check_company=True,
        ondelete='restrict',
    )
    partner_id = fields.Many2one(
        related='case_id.partner_id',
        string='Customer',
        store=True,
        readonly=True,
    )
    vehicle_id = fields.Many2one(
        related='case_id.vehicle_id',
        string='Vehicle',
        store=True,
        readonly=True,
    )
    requested_by_id = fields.Many2one(
        'res.users',
        default=lambda self: self.env.user,
        required=True,
        tracking=True,
    )
    request_date = fields.Datetime(default=fields.Datetime.now, required=True, tracking=True)
    warehouse_id = fields.Many2one(
        'stock.warehouse',
        required=True,
        check_company=True,
        default=lambda self: self._default_warehouse_id(),
    )
    picking_type_id = fields.Many2one(
        'stock.picking.type',
        required=True,
        check_company=True,
        domain="[('code', '=', 'outgoing'), ('warehouse_id', '=', warehouse_id)]",
    )
    location_id = fields.Many2one(
        'stock.location',
        string='Source Location',
        required=True,
        domain="[('usage', '=', 'internal')]",
    )
    location_dest_id = fields.Many2one(
        'stock.location',
        string='Destination Location',
        required=True,
    )
    line_ids = fields.One2many(
        'gara.service.stock.request.line',
        'request_id',
        string='Parts',
        copy=True,
    )
    picking_id = fields.Many2one(
        'stock.picking',
        string='Stock Picking',
        copy=False,
        readonly=True,
        check_company=True,
    )
    picking_state = fields.Selection(related='picking_id.state', string='Picking Status')
    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('confirmed', 'Confirmed'),
            ('picking', 'Picking Created'),
            ('done', 'Done'),
            ('cancel', 'Cancelled'),
        ],
        default='draft',
        required=True,
        tracking=True,
        copy=False,
        index=True,
    )
    note = fields.Text()

    @api.model
    def _default_warehouse_id(self):
        return self.env['stock.warehouse'].search([
            ('company_id', '=', self.env.company.id),
        ], limit=1)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'gara.service.stock.request'
                ) or 'New'
        return super().create(vals_list)

    @api.onchange('company_id')
    def _onchange_company_id(self):
        for rec in self:
            rec.warehouse_id = self.env['stock.warehouse'].search([
                ('company_id', '=', rec.company_id.id),
            ], limit=1)

    @api.onchange('warehouse_id')
    def _onchange_warehouse_id(self):
        for rec in self:
            warehouse = rec.warehouse_id
            rec.picking_type_id = warehouse.out_type_id if warehouse else False
            rec.location_id = warehouse.lot_stock_id if warehouse else False
            rec.location_dest_id = rec._get_customer_location()

    @api.onchange('picking_type_id')
    def _onchange_picking_type_id(self):
        for rec in self:
            picking_type = rec.picking_type_id
            if picking_type:
                rec.location_id = picking_type.default_location_src_id or rec.location_id
                rec.location_dest_id = (
                    picking_type.default_location_dest_id or rec.location_dest_id
                )

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        warehouse = self.env['stock.warehouse'].browse(values.get('warehouse_id'))
        if warehouse:
            values.setdefault('picking_type_id', warehouse.out_type_id.id)
            values.setdefault('location_id', warehouse.lot_stock_id.id)
        values.setdefault('location_dest_id', self._get_customer_location().id)
        return values

    def _get_customer_location(self):
        customer_location, _supplier_location = self.env['stock.warehouse']._get_partner_locations()
        return customer_location

    def _check_has_lines(self):
        for rec in self:
            if not rec.line_ids:
                raise UserError(_('Add at least one part before confirming this request.'))

    def action_confirm(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Only draft requests can be confirmed.'))
            rec._check_has_lines()
            rec.state = 'confirmed'

    def action_create_picking(self):
        for rec in self:
            if rec.state not in ('confirmed', 'draft'):
                raise UserError(_('Only draft or confirmed requests can create a picking.'))
            if rec.picking_id:
                raise UserError(_('A stock picking already exists for this request.'))
            rec._check_has_lines()
            if not rec.picking_type_id:
                raise UserError(_('Configure an outgoing operation type.'))
            picking = self.env['stock.picking'].create(rec._prepare_picking_values())
            picking.action_confirm()
            rec.picking_id = picking.id
            rec.state = 'picking'

    def _prepare_picking_values(self):
        self.ensure_one()
        moves = []
        for line in self.line_ids:
            moves.append((0, 0, line._prepare_stock_move_values()))
        return {
            'partner_id': self.partner_id.id,
            'company_id': self.company_id.id,
            'picking_type_id': self.picking_type_id.id,
            'location_id': self.location_id.id,
            'location_dest_id': self.location_dest_id.id,
            'origin': self.name,
            'gara_service_stock_request_id': self.id,
            'move_ids': moves,
        }

    def action_mark_done(self):
        for rec in self:
            if not rec.picking_id or rec.picking_id.state != 'done':
                raise UserError(_('Validate the linked stock picking before marking done.'))
            rec.state = 'done'

    def action_cancel(self):
        for rec in self:
            if rec.picking_id and rec.picking_id.state not in ('done', 'cancel'):
                rec.picking_id.action_cancel()
            rec.state = 'cancel'

    def action_view_picking(self):
        self.ensure_one()
        if not self.picking_id:
            raise UserError(_('No stock picking has been created.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Stock Picking'),
            'res_model': 'stock.picking',
            'view_mode': 'form',
            'res_id': self.picking_id.id,
        }


class GaraServiceStockRequestLine(models.Model):
    _name = 'gara.service.stock.request.line'
    _description = 'Gara Service Stock Request Line'
    _order = 'request_id, sequence, id'

    request_id = fields.Many2one(
        'gara.service.stock.request',
        required=True,
        ondelete='cascade',
    )
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one(related='request_id.company_id', store=True, readonly=True)
    product_id = fields.Many2one(
        'product.product',
        required=True,
        domain="[('type', 'in', ('product', 'consu'))]",
    )
    name = fields.Char(required=True)
    product_uom_qty = fields.Float(string='Demand', default=1.0, required=True)
    product_uom = fields.Many2one('uom.uom', string='Unit of Measure', required=True)
    note = fields.Char()

    @api.onchange('product_id')
    def _onchange_product_id(self):
        for line in self:
            if line.product_id:
                line.name = line.product_id.display_name
                line.product_uom = line.product_id.uom_id

    @api.constrains('product_uom_qty')
    def _check_product_uom_qty(self):
        for line in self:
            if line.product_uom_qty <= 0:
                raise ValidationError(_('Demand quantity must be positive.'))

    def _prepare_stock_move_values(self):
        self.ensure_one()
        request = self.request_id
        return {
            'name': self.name or self.product_id.display_name,
            'product_id': self.product_id.id,
            'product_uom_qty': self.product_uom_qty,
            'product_uom': self.product_uom.id,
            'location_id': request.location_id.id,
            'location_dest_id': request.location_dest_id.id,
            'company_id': request.company_id.id,
        }
