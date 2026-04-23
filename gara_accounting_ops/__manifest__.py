# -*- coding: utf-8 -*-
{
    'name': 'Zgara Accounting Operations',
    'version': '17.0.1.0.0',
    'category': 'Accounting/Accounting',
    'summary': 'KGara-style accounting document operations for Zgara',
    'description': """
Adds KGara-style accounting operation catalogs and document metadata:
document groups, document reason codes, and a document book on top of
Odoo journal entries and invoices. Adds CSV/XLSX draft invoice and journal
entry import.
""",
    'author': 'aitilen',
    'license': 'LGPL-3',
    'depends': [
        'gara_workshop',
    ],
    'data': [
        'security/ir_model_access.xml',
        'data/accounting_ops_data.xml',
        'views/account_document_views.xml',
        'views/accounting_rule_views.xml',
        'views/allocation_views.xml',
        'views/account_move_views.xml',
        'views/invoice_import_wizard_views.xml',
        'views/journal_entry_import_wizard_views.xml',
        'views/closing_lock_wizard_views.xml',
        'views/opening_balance_wizard_views.xml',
        'views/period_rollover_wizard_views.xml',
        'views/advanced_accounting_wizard_views.xml',
        'views/res_config_settings_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': False,
}
