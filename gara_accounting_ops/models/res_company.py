# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    _inherit = 'res.company'

    gara_enable_accounting_rule_engine = fields.Boolean(
        string='Enable Gara accounting rule engine',
        default=True,
    )
    gara_enable_document_auto_defaults = fields.Boolean(
        string='Apply default document group/reason',
        default=True,
    )
    gara_enable_document_numbering = fields.Boolean(
        string='Enable Gara document numbering',
        default=True,
    )
    gara_document_number_sync_ref = fields.Boolean(
        string='Sync move reference with Gara document number',
        default=False,
    )
    gara_document_number_prefix = fields.Char(
        string='Gara document number prefix',
        default='%(group)s/%(year)s/',
        help='Available tokens: %(group)s %(reason)s %(move_type)s %(year)s %(month)s %(day)s',
    )
    gara_document_number_padding = fields.Integer(
        string='Gara document number padding',
        default=5,
    )
    gara_document_number_next = fields.Integer(
        string='Next Gara document number',
        default=1,
    )
    gara_document_number_reset_yearly = fields.Boolean(
        string='Reset document number yearly',
        default=True,
    )
    gara_document_number_year = fields.Integer(
        string='Document number year',
        default=lambda self: fields.Date.context_today(self).year,
    )

    gara_default_receipt_group_id = fields.Many2one(
        'gara.account.document.group',
        string='Default receipt document group',
        default=lambda self: self._gara_default_group('gara_accounting_ops.document_group_receipt'),
    )
    gara_default_receipt_reason_id = fields.Many2one(
        'gara.account.document.reason',
        string='Default receipt document reason',
        default=lambda self: self._gara_default_reason('gara_accounting_ops.document_reason_service_payment'),
    )
    gara_default_payment_group_id = fields.Many2one(
        'gara.account.document.group',
        string='Default payment document group',
        default=lambda self: self._gara_default_group('gara_accounting_ops.document_group_payment'),
    )
    gara_default_payment_reason_id = fields.Many2one(
        'gara.account.document.reason',
        string='Default payment document reason',
        default=lambda self: self._gara_default_reason('gara_accounting_ops.document_reason_supplier_payment'),
    )
    gara_default_sale_invoice_group_id = fields.Many2one(
        'gara.account.document.group',
        string='Default sale invoice document group',
        default=lambda self: self._gara_default_group('gara_accounting_ops.document_group_sale_invoice'),
    )
    gara_default_sale_invoice_reason_id = fields.Many2one(
        'gara.account.document.reason',
        string='Default sale invoice document reason',
        default=lambda self: self._gara_default_reason('gara_accounting_ops.document_reason_service_invoice'),
    )
    gara_default_purchase_invoice_group_id = fields.Many2one(
        'gara.account.document.group',
        string='Default purchase invoice document group',
        default=lambda self: self._gara_default_group('gara_accounting_ops.document_group_purchase_invoice'),
    )
    gara_default_purchase_invoice_reason_id = fields.Many2one(
        'gara.account.document.reason',
        string='Default purchase invoice document reason',
        default=lambda self: self._gara_default_reason('gara_accounting_ops.document_reason_purchase_parts'),
    )
    gara_default_journal_group_id = fields.Many2one(
        'gara.account.document.group',
        string='Default journal document group',
        default=lambda self: self._gara_default_group('gara_accounting_ops.document_group_journal'),
    )
    gara_default_journal_reason_id = fields.Many2one(
        'gara.account.document.reason',
        string='Default journal document reason',
        default=lambda self: self._gara_default_reason('gara_accounting_ops.document_reason_adjustment'),
    )

    @api.model
    def _gara_default_group(self, xmlid):
        return self.env.ref(xmlid, raise_if_not_found=False)

    @api.model
    def _gara_default_reason(self, xmlid):
        return self.env.ref(xmlid, raise_if_not_found=False)

    @api.constrains(
        'gara_default_receipt_group_id',
        'gara_default_receipt_reason_id',
        'gara_default_payment_group_id',
        'gara_default_payment_reason_id',
        'gara_default_sale_invoice_group_id',
        'gara_default_sale_invoice_reason_id',
        'gara_default_purchase_invoice_group_id',
        'gara_default_purchase_invoice_reason_id',
        'gara_default_journal_group_id',
        'gara_default_journal_reason_id',
        'gara_document_number_padding',
        'gara_document_number_next',
    )
    def _check_gara_accounting_parameters(self):
        for company in self:
            pairs = [
                (company.gara_default_receipt_group_id, company.gara_default_receipt_reason_id),
                (company.gara_default_payment_group_id, company.gara_default_payment_reason_id),
                (company.gara_default_sale_invoice_group_id, company.gara_default_sale_invoice_reason_id),
                (company.gara_default_purchase_invoice_group_id, company.gara_default_purchase_invoice_reason_id),
                (company.gara_default_journal_group_id, company.gara_default_journal_reason_id),
            ]
            for group, reason in pairs:
                if reason and reason.group_id and group and reason.group_id != group:
                    raise ValidationError(
                        _('Default document reason must belong to the selected default document group.')
                    )
            if company.gara_document_number_padding <= 0:
                raise ValidationError(_('Document number padding must be greater than zero.'))
            if company.gara_document_number_next <= 0:
                raise ValidationError(_('Next document number must be greater than zero.'))
