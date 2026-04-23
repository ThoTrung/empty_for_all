# -*- coding: utf-8 -*-
{
    'name': 'Zgara Mobile Security',
    'version': '17.0.1.0.0',
    'category': 'Services/Project',
    'summary': 'KGara-style app role matrix and display settings',
    'description': """
Adds KGara-style configuration for mobile/app feature permissions, list field
visibility and status colors on top of Odoo groups.
""",
    'author': 'aitilen',
    'license': 'LGPL-3',
    'depends': [
        'gara_workshop',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/mobile_security_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': False,
}
