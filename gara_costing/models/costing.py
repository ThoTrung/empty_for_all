# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class GaraCostElement(models.Model):
    _name = 'gara.cost.element'
    _description = 'Gara Cost Element'
    _order = 'sequence, code, name'

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    element_type = fields.Selection(
        [('material', 'Material'), ('labour', 'Labour'), ('overhead', 'Overhead'), ('other', 'Other')],
        default='material',
        required=True,
    )
    account_id = fields.Many2one('account.account', domain="[('deprecated', '=', False)]")
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'The cost element code must be unique.'),
    ]


class GaraProductNorm(models.Model):
    _name = 'gara.product.norm'
    _description = 'Gara Product Cost Norm'
    _order = 'product_tmpl_id, sequence'

    name = fields.Char(required=True)
    code = fields.Char()
    sequence = fields.Integer(default=10)
    product_tmpl_id = fields.Many2one('product.template', required=True, ondelete='cascade')
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, required=True)
    line_ids = fields.One2many('gara.product.norm.line', 'norm_id', string='Norm Lines')
    currency_id = fields.Many2one(related='company_id.currency_id', readonly=True)
    planned_cost = fields.Monetary(compute='_compute_planned_cost', store=True)
    active = fields.Boolean(default=True)
    note = fields.Text()

    @api.depends('line_ids.subtotal')
    def _compute_planned_cost(self):
        for norm in self:
            norm.planned_cost = sum(norm.line_ids.mapped('subtotal'))


class GaraProductNormLine(models.Model):
    _name = 'gara.product.norm.line'
    _description = 'Gara Product Cost Norm Line'
    _order = 'sequence, id'

    norm_id = fields.Many2one('gara.product.norm', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    cost_element_id = fields.Many2one('gara.cost.element', required=True)
    product_id = fields.Many2one('product.product')
    description = fields.Char(required=True)
    quantity = fields.Float(default=1.0, required=True)
    price_unit = fields.Float(default=0.0)
    currency_id = fields.Many2one(related='norm_id.currency_id', readonly=True)
    subtotal = fields.Monetary(compute='_compute_subtotal', store=True)

    @api.depends('quantity', 'price_unit')
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.quantity * line.price_unit

    @api.constrains('quantity')
    def _check_quantity(self):
        for line in self:
            if line.quantity <= 0:
                raise ValidationError(_('Norm quantity must be positive.'))


class GaraProductionOrder(models.Model):
    _name = 'gara.production.order'
    _description = 'Gara Production Order'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_start desc, id desc'

    name = fields.Char(required=True, copy=False, default='New')
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, required=True)
    product_id = fields.Many2one('product.product', required=True)
    norm_id = fields.Many2one('gara.product.norm', domain="[('product_tmpl_id', '=', product_tmpl_id)]")
    product_tmpl_id = fields.Many2one(related='product_id.product_tmpl_id')
    quantity_planned = fields.Float(default=1.0, required=True)
    quantity_done = fields.Float(default=0.0)
    date_start = fields.Date(default=fields.Date.context_today, required=True)
    date_done = fields.Date()
    state = fields.Selection(
        [('draft', 'Draft'), ('confirmed', 'Confirmed'), ('done', 'Done'), ('cancel', 'Cancelled')],
        default='draft',
        tracking=True,
    )
    line_ids = fields.One2many('gara.production.cost.line', 'production_id', string='Cost Lines')
    currency_id = fields.Many2one(related='company_id.currency_id', readonly=True)
    planned_cost = fields.Monetary(compute='_compute_costs', store=True)
    actual_cost = fields.Monetary(compute='_compute_costs', store=True)
    cost_variance = fields.Monetary(compute='_compute_costs', store=True)
    unit_actual_cost = fields.Monetary(compute='_compute_costs', store=True)
    note = fields.Text()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('gara.production.order') or 'New'
        return super().create(vals_list)

    @api.depends('line_ids.amount', 'quantity_done', 'norm_id.planned_cost', 'quantity_planned')
    def _compute_costs(self):
        for order in self:
            order.planned_cost = (order.norm_id.planned_cost or 0.0) * order.quantity_planned
            order.actual_cost = sum(order.line_ids.mapped('amount'))
            order.cost_variance = order.actual_cost - order.planned_cost
            order.unit_actual_cost = order.actual_cost / order.quantity_done if order.quantity_done else 0.0

    def action_confirm(self):
        for order in self:
            if order.state != 'draft':
                continue
            if order.norm_id and not order.line_ids:
                order.line_ids = [
                    (0, 0, {
                        'cost_element_id': line.cost_element_id.id,
                        'product_id': line.product_id.id,
                        'description': line.description,
                        'quantity': line.quantity * order.quantity_planned,
                        'price_unit': line.price_unit,
                    })
                    for line in order.norm_id.line_ids
                ]
            order.state = 'confirmed'

    def action_done(self):
        for order in self:
            if order.quantity_done <= 0:
                raise UserError(_('Finished quantity must be positive before completing production.'))
            order.write({'state': 'done', 'date_done': fields.Date.context_today(order)})

    def action_cancel(self):
        self.write({'state': 'cancel'})


class GaraProductionCostLine(models.Model):
    _name = 'gara.production.cost.line'
    _description = 'Gara Production Cost Line'
    _order = 'production_id, sequence, id'

    production_id = fields.Many2one('gara.production.order', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    cost_element_id = fields.Many2one('gara.cost.element', required=True)
    product_id = fields.Many2one('product.product')
    description = fields.Char(required=True)
    quantity = fields.Float(default=1.0, required=True)
    price_unit = fields.Float(default=0.0)
    currency_id = fields.Many2one(related='production_id.currency_id', readonly=True)
    amount = fields.Monetary(compute='_compute_amount', store=True)

    @api.depends('quantity', 'price_unit')
    def _compute_amount(self):
        for line in self:
            line.amount = line.quantity * line.price_unit


class GaraWipOpening(models.Model):
    _name = 'gara.wip.opening'
    _description = 'Gara WIP Opening Balance'
    _order = 'date desc, id desc'

    name = fields.Char(required=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, required=True)
    date = fields.Date(default=fields.Date.context_today, required=True)
    product_id = fields.Many2one('product.product', required=True)
    quantity = fields.Float(default=0.0)
    currency_id = fields.Many2one(related='company_id.currency_id', readonly=True)
    amount = fields.Monetary(required=True)
    note = fields.Text()
