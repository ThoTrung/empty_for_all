# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class GaraSimpleCatalogMixin(models.AbstractModel):
    _name = 'gara.simple.catalog.mixin'
    _description = 'Gara Simple Catalog Mixin'
    _order = 'sequence, name'

    name = fields.Char(required=True, translate=True)
    code = fields.Char()
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    note = fields.Text()

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'The code must be unique.'),
    ]


class GaraRevenueType(models.Model):
    _name = 'gara.revenue.type'
    _description = 'Gara Revenue Type'
    _inherit = ['gara.simple.catalog.mixin']
    _order = 'sequence, code, name'

    company_id = fields.Many2one(
        'res.company',
        default=lambda self: self.env.company,
        index=True,
    )
    income_account_id = fields.Many2one(
        'account.account',
        string='Income Account',
        domain="[('deprecated', '=', False), ('account_type', '=', 'income')]",
        check_company=True,
    )
    product_category_id = fields.Many2one('product.category')

    _sql_constraints = [
        (
            'code_company_unique',
            'unique(code, company_id)',
            'The revenue type code must be unique per company.',
        ),
    ]


class GaraMembershipType(models.Model):
    _name = 'gara.membership.type'
    _description = 'Gara Membership Type'
    _inherit = ['gara.simple.catalog.mixin']
    _order = 'sequence, name'

    discount_percent = fields.Float(default=0.0)

    @api.constrains('discount_percent')
    def _check_discount_percent(self):
        for rec in self:
            if rec.discount_percent < 0 or rec.discount_percent > 100:
                raise ValidationError('Discount percent must be between 0 and 100.')


class GaraProductType(models.Model):
    _name = 'gara.product.type'
    _description = 'Gara Product Type'
    _inherit = ['gara.simple.catalog.mixin']
    _parent_name = 'parent_id'
    _parent_store = True

    parent_id = fields.Many2one('gara.product.type', index=True, ondelete='restrict')
    parent_path = fields.Char(index=True, unaccent=False)


class GaraServicePackage(models.Model):
    _name = 'gara.service.package'
    _description = 'Gara Service Package'
    _inherit = ['gara.simple.catalog.mixin']
    _order = 'sequence, code, name'

    company_id = fields.Many2one(
        'res.company',
        default=lambda self: self.env.company,
        index=True,
    )
    service_product_id = fields.Many2one(
        'product.template',
        string='Service Product',
        domain="[('type', '=', 'service')]",
        help='Optional sellable service product representing this package on quotations.',
    )
    line_ids = fields.One2many(
        'gara.service.package.line',
        'package_id',
        string='Package Lines',
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
        readonly=True,
    )
    amount_untaxed = fields.Monetary(
        compute='_compute_amount_untaxed',
        string='Untaxed Amount',
    )

    @api.depends('line_ids.subtotal')
    def _compute_amount_untaxed(self):
        for package in self:
            package.amount_untaxed = sum(package.line_ids.mapped('subtotal'))

    _sql_constraints = [
        (
            'code_company_unique',
            'unique(code, company_id)',
            'The service package code must be unique per company.',
        ),
    ]


class GaraServicePackageLine(models.Model):
    _name = 'gara.service.package.line'
    _description = 'Gara Service Package Line'
    _order = 'sequence, id'

    package_id = fields.Many2one(
        'gara.service.package',
        required=True,
        ondelete='cascade',
    )
    sequence = fields.Integer(default=10)
    product_id = fields.Many2one('product.product', required=True)
    name = fields.Char(required=True)
    product_uom_id = fields.Many2one('uom.uom', string='Unit of Measure')
    quantity = fields.Float(default=1.0, required=True)
    price_unit = fields.Float(string='Unit Price')
    discount = fields.Float(default=0.0)
    currency_id = fields.Many2one(
        'res.currency',
        related='package_id.currency_id',
        readonly=True,
    )
    subtotal = fields.Monetary(compute='_compute_subtotal', store=True)

    @api.onchange('product_id')
    def _onchange_product_id(self):
        for line in self:
            if not line.product_id:
                continue
            line.name = line.product_id.display_name
            line.product_uom_id = line.product_id.uom_id
            line.price_unit = line.product_id.lst_price

    @api.depends('quantity', 'price_unit', 'discount')
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.quantity * line.price_unit * (1 - (line.discount or 0.0) / 100.0)

    @api.constrains('quantity', 'discount')
    def _check_quantity_and_discount(self):
        for line in self:
            if line.quantity <= 0:
                raise ValidationError('Package line quantity must be positive.')
            if line.discount < 0 or line.discount > 100:
                raise ValidationError('Package line discount must be between 0 and 100.')


class GaraCustomerSource(models.Model):
    _name = 'gara.customer.source'
    _description = 'Gara Customer Source'
    _inherit = ['gara.simple.catalog.mixin']


class GaraCustomerStatus(models.Model):
    _name = 'gara.customer.status'
    _description = 'Gara Customer Status'
    _inherit = ['gara.simple.catalog.mixin']

    color = fields.Integer()


class GaraCustomerType(models.Model):
    _name = 'gara.customer.type'
    _description = 'Gara Customer Type'
    _inherit = ['gara.simple.catalog.mixin']


class GaraCareType(models.Model):
    _name = 'gara.care.type'
    _description = 'Gara Care Type'
    _inherit = ['gara.simple.catalog.mixin']


class GaraCareResult(models.Model):
    _name = 'gara.care.result'
    _description = 'Gara Care Result'
    _inherit = ['gara.simple.catalog.mixin']

    color = fields.Integer()


class GaraCareResultDetail(models.Model):
    _name = 'gara.care.result.detail'
    _description = 'Gara Care Result Detail'
    _inherit = ['gara.simple.catalog.mixin']

    result_id = fields.Many2one('gara.care.result', required=True, ondelete='cascade')

    _sql_constraints = [
        (
            'code_result_unique',
            'unique(code, result_id)',
            'The detail code must be unique per care result.',
        ),
    ]


class GaraBankBranch(models.Model):
    _name = 'gara.bank.branch'
    _description = 'Gara Bank Branch'
    _inherit = ['gara.simple.catalog.mixin']
    _rec_name = 'display_name'

    bank_id = fields.Many2one('res.bank', required=True, ondelete='cascade')
    street = fields.Char()
    city = fields.Char()
    display_name = fields.Char(compute='_compute_display_name', store=True)

    @api.depends('name', 'code', 'bank_id.name')
    def _compute_display_name(self):
        for rec in self:
            parts = [rec.bank_id.name, rec.name]
            if rec.code:
                parts.append('[%s]' % rec.code)
            rec.display_name = ' - '.join(part for part in parts if part)

    _sql_constraints = [
        (
            'code_bank_unique',
            'unique(code, bank_id)',
            'The branch code must be unique per bank.',
        ),
    ]


class GaraPrintGroup(models.Model):
    _name = 'gara.print.group'
    _description = 'Gara Print Group'
    _inherit = ['gara.simple.catalog.mixin']

    model_name = fields.Char(
        help='Technical model name used to group print templates, for example sale.order.',
    )


class GaraPaymentMethod(models.Model):
    _name = 'gara.payment.method'
    _description = 'Gara Payment Method'
    _inherit = ['gara.simple.catalog.mixin']

    journal_id = fields.Many2one(
        'account.journal',
        domain="[('type', 'in', ('cash', 'bank'))]",
    )
    payment_type = fields.Selection(
        [('cash', 'Cash'), ('bank', 'Bank Transfer'), ('card', 'Card'), ('other', 'Other')],
        default='cash',
        required=True,
    )


class GaraBankAccount(models.Model):
    _name = 'gara.bank.account'
    _description = 'Gara Bank Account'
    _inherit = ['gara.simple.catalog.mixin']
    _rec_name = 'display_name'

    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, required=True)
    bank_id = fields.Many2one('res.bank')
    branch_id = fields.Many2one('gara.bank.branch')
    account_number = fields.Char(required=True)
    account_holder = fields.Char()
    journal_id = fields.Many2one(
        'account.journal',
        domain="[('company_id', '=', company_id), ('type', '=', 'bank')]",
    )
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    display_name = fields.Char(compute='_compute_display_name', store=True)

    @api.depends('account_number', 'bank_id.name', 'account_holder')
    def _compute_display_name(self):
        for rec in self:
            parts = [rec.bank_id.name, rec.account_number, rec.account_holder]
            rec.display_name = ' - '.join(part for part in parts if part)

    _sql_constraints = [
        ('account_company_unique', 'unique(account_number, company_id)', 'The bank account must be unique per company.'),
    ]


class GaraCaseType(models.Model):
    _name = 'gara.case.type'
    _description = 'Gara Case Type'
    _inherit = ['gara.simple.catalog.mixin']

    color = fields.Integer()


class GaraCostItem(models.Model):
    _name = 'gara.cost.item'
    _description = 'Gara Cost Item'
    _inherit = ['gara.simple.catalog.mixin']

    account_id = fields.Many2one('account.account', domain="[('deprecated', '=', False)]")
    item_type = fields.Selection(
        [('revenue', 'Revenue'), ('cost', 'Cost'), ('expense', 'Expense'), ('other', 'Other')],
        default='expense',
        required=True,
    )
