# -*- coding: utf-8 -*-
{
    'name': 'Zgara Care Integration',
    'version': '17.0.1.0.0',
    'category': 'Services/Customer Care',
    'summary': 'KGara-style SMS/Zalo/call templates and communication logs',
    'description': """
Adds provider configuration, message templates, interaction logs, and generic
HTTP JSON delivery for SMS/Zalo customer care flows.
""",
    'author': 'aitilen',
    'license': 'LGPL-3',
    'depends': [
        'gara_workshop',
    ],
    'data': [
        'security/ir_model_access.xml',
        'data/ir_cron.xml',
        'views/care_integration_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': False,
}
