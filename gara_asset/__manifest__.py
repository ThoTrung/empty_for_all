# -*- coding: utf-8 -*-
{
    'name': 'Zgara Fixed Assets',
    'version': '17.0.1.0.0',
    'category': 'Accounting/Accounting',
    'summary': 'KGara-style fixed asset groups, assets and depreciation',
    'description': """
Adds lightweight fixed asset management for Zgara: asset categories, asset
records, depreciation schedules and draft accounting entries.
""",
    'author': 'aitilen',
    'license': 'LGPL-3',
    'depends': [
        'gara_workshop',
        'account',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/gara_asset_data.xml',
        'views/gara_asset_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': False,
}
