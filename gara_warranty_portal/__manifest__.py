# -*- coding: utf-8 -*-
{
    'name': 'Zgara Warranty Lookup',
    'version': '17.0.1.0.0',
    'category': 'Services/Warranty',
    'summary': 'KGara-style warranty lookup',
    'description': 'Adds internal warranty lookup by vehicle, serial, customer, and claim reference.',
    'author': 'aitilen',
    'license': 'LGPL-3',
    'depends': ['gara_workshop'],
    'data': [
        'security/ir_model_access.xml',
        'views/warranty_claim_views.xml',
        'wizards/warranty_lookup_wizard_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': False,
}
