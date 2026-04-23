# -*- coding: utf-8 -*-

from odoo import fields, models


class GaraAccountDocumentGroup(models.Model):
    _name = 'gara.account.document.group'
    _description = 'Gara Accounting Document Group'
    _order = 'sequence, code, name'

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    journal_ids = fields.Many2many(
        'account.journal',
        'gara_account_document_group_journal_rel',
        'group_id',
        'journal_id',
        string='Allowed Journals',
        help='Optional journals commonly used for this KGara document group.',
    )
    default_reason_id = fields.Many2one(
        'gara.account.document.reason',
        string='Default Reason',
    )
    note = fields.Text()

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'The document group code must be unique.'),
    ]


class GaraAccountDocumentReason(models.Model):
    _name = 'gara.account.document.reason'
    _description = 'Gara Accounting Document Reason'
    _order = 'sequence, code, name'

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    group_id = fields.Many2one(
        'gara.account.document.group',
        string='Document Group',
        ondelete='restrict',
    )
    note = fields.Text()

    _sql_constraints = [
        (
            'code_group_unique',
            'unique(code, group_id)',
            'The reason code must be unique per document group.',
        ),
    ]


class GaraClosingConfig(models.Model):
    _name = 'gara.closing.config'
    _description = 'Gara Closing Configuration'
    _order = 'company_id, sequence, name'

    name = fields.Char(required=True)
    company_id = fields.Many2one(
        'res.company',
        required=True,
        default=lambda self: self.env.company,
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    source_account_ids = fields.Many2many(
        'account.account',
        'gara_closing_config_source_account_rel',
        'config_id',
        'account_id',
        string='Source Accounts',
    )
    destination_account_id = fields.Many2one(
        'account.account',
        string='Destination Account',
        check_company=True,
    )
    journal_id = fields.Many2one(
        'account.journal',
        domain="[('company_id', '=', company_id), ('type', '=', 'general')]",
    )
    note = fields.Text()
