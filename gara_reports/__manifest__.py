# -*- coding: utf-8 -*-
{
    'name': 'Zgara Reports',
    'version': '17.0.1.0.0',
    'category': 'Reporting',
    'summary': 'KGara-style operational reports for Zgara',
    'description': """
Adds KGara-style service and stock reporting views on top of Zgara workshop,
accounting, and inventory data.
""",
    'author': 'aitilen',
    'license': 'LGPL-3',
    'depends': [
        'gara_stock_service',
        'gara_accounting_ops',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/service_case_report_views.xml',
        'views/stock_ledger_report_views.xml',
        'views/account_report_views.xml',
        'views/currency_report_views.xml',
        'views/report_templates.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': False,
}
