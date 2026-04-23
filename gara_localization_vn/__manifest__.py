# -*- coding: utf-8 -*-
{
    'name': 'Zgara Vietnam Localization',
    'version': '17.0.1.0.0',
    'category': 'Localization',
    'summary': 'KGara-style Vietnam province, district and ward catalogs',
    'description': """
Adds Vietnam administrative address catalogs and links them to contacts so Zgara
can capture KGara-style Province/District/Ward addresses.
""",
    'author': 'aitilen',
    'license': 'LGPL-3',
    'depends': [
        'gara_workshop',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/vn_address_data.xml',
        'views/vn_address_views.xml',
        'views/res_partner_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': False,
}
