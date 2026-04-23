# -*- coding: utf-8 -*-
{
    'name': 'Zgara Costing',
    'version': '17.0.1.0.0',
    'category': 'Manufacturing/Manufacturing',
    'summary': 'KGara-style costing and production tracking',
    'description': """
Adds lightweight KGara-style costing structures: product norms, production
orders, production cost lines, finished quantity evaluation and WIP opening.
""",
    'author': 'aitilen',
    'license': 'LGPL-3',
    'depends': [
        'gara_master_data',
        'gara_stock_service',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/sequence_data.xml',
        'views/costing_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': False,
}
