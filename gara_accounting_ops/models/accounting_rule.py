# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class GaraAccountingRule(models.Model):
    _name = 'gara.accounting.rule'
    _description = 'Gara accounting rule'
    _order = 'sequence, id'

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    move_type = fields.Selection(
        selection=[
            ('all', 'All'),
            ('entry', 'Journal Entry'),
            ('out_invoice', 'Customer Invoice'),
            ('out_refund', 'Customer Credit Note'),
            ('out_receipt', 'Sales Receipt'),
            ('in_invoice', 'Vendor Bill'),
            ('in_refund', 'Vendor Credit Note'),
            ('in_receipt', 'Purchase Receipt'),
        ],
        default='all',
        required=True,
    )
    business_type = fields.Selection(
        selection=[
            ('all', 'All'),
            ('service', 'Service'),
            ('parts', 'Parts'),
            ('insurance', 'Insurance'),
            ('other', 'Other'),
        ],
        default='all',
        required=True,
    )
    partner_scope = fields.Selection(
        selection=[
            ('all', 'All'),
            ('customer', 'Customer'),
            ('supplier', 'Supplier'),
            ('insurance', 'Insurance'),
        ],
        default='all',
        required=True,
    )
    payment_channel = fields.Selection(
        selection=[
            ('all', 'All'),
            ('cash', 'Cash'),
            ('bank', 'Bank Transfer'),
            ('card', 'Card'),
            ('ewallet', 'E-Wallet'),
            ('other', 'Other'),
        ],
        default='all',
        required=True,
    )
    tax_scope = fields.Selection(
        selection=[
            ('all', 'All'),
            ('vat', 'VAT'),
            ('non_vat', 'Non VAT'),
        ],
        default='all',
        required=True,
    )
    output_journal_id = fields.Many2one(
        'account.journal',
        string='Output Journal',
        check_company=True,
        domain="[('company_id', '=', company_id)]",
    )
    output_document_group_id = fields.Many2one(
        'gara.account.document.group',
        string='Output Document Group',
    )
    output_document_reason_id = fields.Many2one(
        'gara.account.document.reason',
        string='Output Document Reason',
        domain="['|', ('group_id', '=', False), ('group_id', '=', output_document_group_id)]",
    )
    output_income_account_id = fields.Many2one(
        'account.account',
        string='Output Income Account',
        check_company=True,
        domain="[('company_id', '=', company_id), ('deprecated', '=', False)]",
    )
    output_expense_account_id = fields.Many2one(
        'account.account',
        string='Output Expense Account',
        check_company=True,
        domain="[('company_id', '=', company_id), ('deprecated', '=', False)]",
    )
    note = fields.Text()

    @api.constrains('output_document_group_id', 'output_document_reason_id')
    def _check_reason_group(self):
        for rule in self:
            reason = rule.output_document_reason_id
            group = rule.output_document_group_id
            if reason and reason.group_id and group and reason.group_id != group:
                raise ValidationError(
                    _('Output document reason must belong to output document group.')
                )

    def _match_move(self, move):
        self.ensure_one()
        if self.move_type != 'all' and self.move_type != move.move_type:
            return False
        if self.business_type != 'all' and self.business_type != move.gara_business_type:
            return False
        if self.payment_channel != 'all' and self.payment_channel != move.gara_payment_channel:
            return False
        if self.tax_scope != 'all' and self.tax_scope != move.gara_tax_scope:
            return False
        if self.partner_scope != 'all' and self.partner_scope != move._gara_partner_scope():
            return False
        return True


class GaraDocumentSequenceRule(models.Model):
    _name = 'gara.document.sequence.rule'
    _description = 'Gara document sequence rule'
    _order = 'sequence, id'

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    move_type = fields.Selection(
        selection=[
            ('all', 'All'),
            ('entry', 'Journal Entry'),
            ('out_invoice', 'Customer Invoice'),
            ('out_refund', 'Customer Credit Note'),
            ('out_receipt', 'Sales Receipt'),
            ('in_invoice', 'Vendor Bill'),
            ('in_refund', 'Vendor Credit Note'),
            ('in_receipt', 'Purchase Receipt'),
        ],
        default='all',
        required=True,
    )
    document_group_id = fields.Many2one('gara.account.document.group')
    document_reason_id = fields.Many2one(
        'gara.account.document.reason',
        domain="['|', ('group_id', '=', False), ('group_id', '=', document_group_id)]",
    )
    prefix = fields.Char(
        default='%(group)s/%(year)s/',
        required=True,
        help='Available tokens: %(group)s %(reason)s %(move_type)s %(year)s %(month)s %(day)s',
    )
    padding = fields.Integer(default=5, required=True)
    number_next = fields.Integer(default=1, required=True)
    reset_yearly = fields.Boolean(default=True)
    current_year = fields.Integer(default=lambda self: fields.Date.context_today(self).year)

    @api.constrains('document_group_id', 'document_reason_id', 'padding', 'number_next')
    def _check_sequence_rule(self):
        for rule in self:
            if (
                rule.document_reason_id
                and rule.document_reason_id.group_id
                and rule.document_group_id
                and rule.document_reason_id.group_id != rule.document_group_id
            ):
                raise ValidationError(_('Document reason must belong to the selected document group.'))
            if rule.padding <= 0:
                raise ValidationError(_('Padding must be greater than zero.'))
            if rule.number_next <= 0:
                raise ValidationError(_('Next number must be greater than zero.'))

    def _match_move(self, move):
        self.ensure_one()
        if self.move_type != 'all' and self.move_type != move.move_type:
            return False
        if self.document_group_id and move.gara_document_group_id != self.document_group_id:
            return False
        if self.document_reason_id and move.gara_document_reason_id != self.document_reason_id:
            return False
        return True

    @api.model
    def _format_number(self, prefix, padding, number):
        return '%s%s' % (prefix or '', str(number).zfill(padding))

    def _render_prefix(self, move, year):
        self.ensure_one()
        move_date = move.date or fields.Date.context_today(move)
        group_code = (move.gara_document_group_id.code or move.move_type or '').upper()
        reason_code = (move.gara_document_reason_id.code or '').upper()
        tokens = {
            'group': group_code,
            'reason': reason_code,
            'move_type': (move.move_type or '').upper(),
            'year': str(year),
            'month': str(move_date.month).zfill(2),
            'day': str(move_date.day).zfill(2),
        }
        try:
            return (self.prefix or '') % tokens
        except Exception:
            return self.prefix or ''

    def next_by_move(self, move):
        self.ensure_one()
        move_date = move.date or fields.Date.context_today(move)
        year = move_date.year
        if self.reset_yearly and self.current_year != year:
            self.write({'current_year': year, 'number_next': 1})
        number = self.number_next
        self.write({'number_next': number + 1, 'current_year': year})
        return self._format_number(
            self._render_prefix(move, year),
            self.padding,
            number,
        )
