# -*- coding: utf-8 -*-
{
    'name': 'Zgara BI',
    'version': '17.0.1.0.0',
    'category': 'Reporting',
    'summary': 'KGara-style BI dashboard aggregates for Zgara',
    'description': """
Adds read-only BI aggregates for management dashboards using the operational
reports already available in Zgara.
""",
    'author': 'aitilen',
    'license': 'LGPL-3',
    'depends': [
        'gara_reports',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/bi_dashboard_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': False,
}
