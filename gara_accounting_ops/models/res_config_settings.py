# -*- coding: utf-8 -*-

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    gara_enable_accounting_rule_engine = fields.Boolean(
        related='company_id.gara_enable_accounting_rule_engine',
        readonly=False,
    )
    gara_enable_document_auto_defaults = fields.Boolean(
        related='company_id.gara_enable_document_auto_defaults',
        readonly=False,
    )
    gara_enable_document_numbering = fields.Boolean(
        related='company_id.gara_enable_document_numbering',
        readonly=False,
    )
    gara_document_number_sync_ref = fields.Boolean(
        related='company_id.gara_document_number_sync_ref',
        readonly=False,
    )
    gara_document_number_prefix = fields.Char(
        related='company_id.gara_document_number_prefix',
        readonly=False,
    )
    gara_document_number_padding = fields.Integer(
        related='company_id.gara_document_number_padding',
        readonly=False,
    )
    gara_document_number_next = fields.Integer(
        related='company_id.gara_document_number_next',
        readonly=False,
    )
    gara_document_number_reset_yearly = fields.Boolean(
        related='company_id.gara_document_number_reset_yearly',
        readonly=False,
    )

    gara_default_receipt_group_id = fields.Many2one(
        related='company_id.gara_default_receipt_group_id',
        readonly=False,
    )
    gara_default_receipt_reason_id = fields.Many2one(
        related='company_id.gara_default_receipt_reason_id',
        readonly=False,
    )
    gara_default_payment_group_id = fields.Many2one(
        related='company_id.gara_default_payment_group_id',
        readonly=False,
    )
    gara_default_payment_reason_id = fields.Many2one(
        related='company_id.gara_default_payment_reason_id',
        readonly=False,
    )
    gara_default_sale_invoice_group_id = fields.Many2one(
        related='company_id.gara_default_sale_invoice_group_id',
        readonly=False,
    )
    gara_default_sale_invoice_reason_id = fields.Many2one(
        related='company_id.gara_default_sale_invoice_reason_id',
        readonly=False,
    )
    gara_default_purchase_invoice_group_id = fields.Many2one(
        related='company_id.gara_default_purchase_invoice_group_id',
        readonly=False,
    )
    gara_default_purchase_invoice_reason_id = fields.Many2one(
        related='company_id.gara_default_purchase_invoice_reason_id',
        readonly=False,
    )
    gara_default_journal_group_id = fields.Many2one(
        related='company_id.gara_default_journal_group_id',
        readonly=False,
    )
    gara_default_journal_reason_id = fields.Many2one(
        related='company_id.gara_default_journal_reason_id',
        readonly=False,
    )
