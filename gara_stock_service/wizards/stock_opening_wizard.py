# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare


class GaraStockOpeningWizard(models.TransientModel):
    _name = 'gara.stock.opening.wizard'
    _description = 'KGara-style stock opening wizard'

    company_id = fields.Many2one(
        'res.company',
        required=True,
        default=lambda self: self.env.company,
    )
    opening_date = fields.Date(required=True, default=fields.Date.context_today)
    location_id = fields.Many2one(
        'stock.location',
        required=True,
        domain="[('usage', '=', 'internal')]",
        default=lambda self: self._default_location_id(),
    )
    set_standard_cost = fields.Boolean(
        string='Update standard cost from opening lines',
        default=False,
    )
    line_ids = fields.One2many('gara.stock.opening.wizard.line', 'wizard_id')
    note = fields.Text()

    @api.model
    def _default_location_id(self):
        warehouse = self.env['stock.warehouse'].search([
            ('company_id', '=', self.env.company.id),
        ], limit=1)
        if warehouse:
            return warehouse.lot_stock_id
        return self.env['stock.location'].search([
            ('usage', '=', 'internal'),
            ('company_id', 'in', [False, self.env.company.id]),
        ], limit=1)

    @api.onchange('location_id')
    def _onchange_location_id(self):
        for wizard in self:
            for line in wizard.line_ids:
                if not line.product_id:
                    continue
                qty = self.env['stock.quant']._get_available_quantity(
                    line.product_id,
                    wizard.location_id,
                    allow_negative=True,
                )
                line.current_qty = qty
                line.opening_qty = qty

    def action_load_current_stock(self):
        self.ensure_one()
        if not self.location_id:
            raise UserError(_('Select an internal location first.'))
        grouped = self.env['stock.quant'].read_group(
            [
                ('company_id', '=', self.company_id.id),
                ('location_id', 'child_of', self.location_id.id),
                ('product_id.type', 'in', ('product', 'consu')),
            ],
            ['quantity:sum'],
            ['product_id'],
            lazy=False,
        )
        if not grouped:
            raise UserError(_('No stock quant found at the selected location.'))
        product_model = self.env['product.product']
        line_vals = []
        for item in grouped:
            product_data = item.get('product_id')
            if not product_data:
                continue
            product = product_model.browse(product_data[0])
            qty = item.get('quantity') or 0.0
            line_vals.append((0, 0, {
                'product_id': product.id,
                'current_qty': qty,
                'opening_qty': qty,
                'unit_cost': product.standard_price,
            }))
        self.write({'line_ids': [(5, 0, 0)] + line_vals})
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_apply(self):
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_('Add at least one opening stock line.'))
        quant_model = self.env['stock.quant'].with_company(self.company_id).sudo()
        opening_dt = fields.Datetime.to_datetime('%s 00:00:00' % self.opening_date)
        for line in self.line_ids:
            current_qty = quant_model._get_available_quantity(
                line.product_id,
                self.location_id,
                allow_negative=True,
            )
            qty_diff = line.opening_qty - current_qty
            if float_compare(
                qty_diff,
                0.0,
                precision_rounding=line.product_id.uom_id.rounding,
            ):
                quant_model._update_available_quantity(
                    line.product_id,
                    self.location_id,
                    quantity=qty_diff,
                    in_date=opening_dt,
                )
            if self.set_standard_cost:
                line.product_id.with_company(self.company_id).standard_price = line.unit_cost
        return {'type': 'ir.actions.act_window_close'}


class GaraStockOpeningWizardLine(models.TransientModel):
    _name = 'gara.stock.opening.wizard.line'
    _description = 'KGara stock opening line'

    wizard_id = fields.Many2one(
        'gara.stock.opening.wizard',
        required=True,
        ondelete='cascade',
    )
    company_id = fields.Many2one(related='wizard_id.company_id')
    product_id = fields.Many2one(
        'product.product',
        required=True,
        domain="[('type', 'in', ('product', 'consu'))]",
    )
    uom_id = fields.Many2one(related='product_id.uom_id', readonly=True)
    current_qty = fields.Float(readonly=True)
    opening_qty = fields.Float(required=True, default=0.0)
    difference_qty = fields.Float(compute='_compute_difference_qty')
    unit_cost = fields.Float()
    note = fields.Char()

    @api.depends('opening_qty', 'current_qty')
    def _compute_difference_qty(self):
        for line in self:
            line.difference_qty = line.opening_qty - line.current_qty

    @api.onchange('product_id')
    def _onchange_product_id(self):
        for line in self:
            if not line.product_id:
                continue
            line.unit_cost = line.product_id.standard_price
            location = line.wizard_id.location_id
            qty = self.env['stock.quant']._get_available_quantity(
                line.product_id,
                location,
                allow_negative=True,
            ) if location else 0.0
            line.current_qty = qty
            line.opening_qty = qty

    @api.constrains('opening_qty', 'unit_cost')
    def _check_values(self):
        for line in self:
            if line.opening_qty < 0:
                raise ValidationError(_('Opening quantity must be non-negative.'))
            if line.unit_cost < 0:
                raise ValidationError(_('Unit cost must be non-negative.'))
