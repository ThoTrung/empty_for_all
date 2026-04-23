# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class GaraStockInventoryBatch(models.Model):
    _name = 'gara.stock.inventory.batch'
    _description = 'Gara Stock Inventory Batch'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'inventory_date desc, id desc'

    name = fields.Char(required=True, copy=False, readonly=True, default='New')
    company_id = fields.Many2one(
        'res.company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    inventory_date = fields.Datetime(default=fields.Datetime.now, required=True, tracking=True)
    warehouse_id = fields.Many2one(
        'stock.warehouse',
        required=True,
        check_company=True,
        default=lambda self: self._default_warehouse_id(),
    )
    location_id = fields.Many2one(
        'stock.location',
        required=True,
        domain="[('usage', '=', 'internal')]",
    )
    responsible_id = fields.Many2one(
        'res.users',
        default=lambda self: self.env.user,
        required=True,
        tracking=True,
    )
    line_ids = fields.One2many(
        'gara.stock.inventory.batch.line',
        'batch_id',
        string='Inventory Lines',
        copy=True,
    )
    line_count = fields.Integer(compute='_compute_line_count')
    difference_line_count = fields.Integer(compute='_compute_line_count')
    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('confirmed', 'Confirmed'),
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
                    'gara.stock.inventory.batch'
                ) or 'New'
        return super().create(vals_list)

    @api.depends('line_ids', 'line_ids.difference_qty')
    def _compute_line_count(self):
        for batch in self:
            batch.line_count = len(batch.line_ids)
            batch.difference_line_count = len(batch.line_ids.filtered('difference_qty'))

    @api.onchange('company_id')
    def _onchange_company_id(self):
        for batch in self:
            batch.warehouse_id = self.env['stock.warehouse'].search([
                ('company_id', '=', batch.company_id.id),
            ], limit=1)

    @api.onchange('warehouse_id')
    def _onchange_warehouse_id(self):
        for batch in self:
            batch.location_id = batch.warehouse_id.lot_stock_id if batch.warehouse_id else False

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        warehouse = self.env['stock.warehouse'].browse(values.get('warehouse_id'))
        if warehouse:
            values.setdefault('location_id', warehouse.lot_stock_id.id)
        return values

    def action_load_products(self):
        for batch in self:
            if batch.state != 'draft':
                raise UserError(_('Only draft inventory batches can load products.'))
            if not batch.location_id:
                raise UserError(_('Select an internal location first.'))
            quants = self.env['stock.quant'].search([
                ('company_id', '=', batch.company_id.id),
                ('location_id', 'child_of', batch.location_id.id),
                ('product_id.type', 'in', ('product', 'consu')),
            ])
            existing_products = batch.line_ids.mapped('product_id')
            lines = []
            for quant in quants:
                if quant.product_id in existing_products:
                    continue
                lines.append((0, 0, {
                    'product_id': quant.product_id.id,
                    'product_uom_id': quant.product_id.uom_id.id,
                    'theoretical_qty': quant.quantity,
                    'counted_qty': quant.quantity,
                }))
                existing_products |= quant.product_id
            if lines:
                batch.write({'line_ids': lines})

    def action_confirm(self):
        for batch in self:
            if batch.state != 'draft':
                raise UserError(_('Only draft inventory batches can be confirmed.'))
            if not batch.line_ids:
                raise UserError(_('Add at least one inventory line before confirming.'))
            batch.line_ids._refresh_theoretical_qty()
            batch.state = 'confirmed'

    def action_done(self):
        for batch in self:
            if batch.state != 'confirmed':
                raise UserError(_('Only confirmed inventory batches can be marked done.'))
            batch.state = 'done'

    def action_cancel(self):
        for batch in self:
            batch.state = 'cancel'


class GaraStockInventoryBatchLine(models.Model):
    _name = 'gara.stock.inventory.batch.line'
    _description = 'Gara Stock Inventory Batch Line'
    _order = 'batch_id, sequence, id'

    batch_id = fields.Many2one(
        'gara.stock.inventory.batch',
        required=True,
        ondelete='cascade',
    )
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one(related='batch_id.company_id', store=True, readonly=True)
    inventory_date = fields.Datetime(related='batch_id.inventory_date', store=True, readonly=True)
    warehouse_id = fields.Many2one(related='batch_id.warehouse_id', store=True, readonly=True)
    location_id = fields.Many2one(related='batch_id.location_id', store=True, readonly=True)
    product_id = fields.Many2one(
        'product.product',
        required=True,
        domain="[('type', 'in', ('product', 'consu'))]",
    )
    product_uom_id = fields.Many2one('uom.uom', string='Unit of Measure', required=True)
    theoretical_qty = fields.Float(readonly=True)
    counted_qty = fields.Float(required=True, default=0.0)
    difference_qty = fields.Float(compute='_compute_difference_qty', store=True)
    note = fields.Char()

    @api.onchange('product_id')
    def _onchange_product_id(self):
        for line in self:
            if line.product_id:
                line.product_uom_id = line.product_id.uom_id

    @api.depends('counted_qty', 'theoretical_qty')
    def _compute_difference_qty(self):
        for line in self:
            line.difference_qty = line.counted_qty - line.theoretical_qty

    @api.constrains('counted_qty')
    def _check_counted_qty(self):
        for line in self:
            if line.counted_qty < 0:
                raise ValidationError(_('Counted quantity cannot be negative.'))

    def _refresh_theoretical_qty(self):
        for line in self:
            qty = self.env['stock.quant']._get_available_quantity(
                line.product_id,
                line.location_id,
            )
            line.theoretical_qty = qty
