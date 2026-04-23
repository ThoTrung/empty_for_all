# -*- coding: utf-8 -*-
{
    'name': 'Zgara Master Data',
    'version': '17.0.1.0.0',
    'category': 'Services/Project',
    'summary': 'KGara-style configurable master data for Zgara',
    'description': """
Adds configurable master data that KGara exposes as separate catalogs:
revenue types, customer classifications, care result taxonomies, bank branches,
print groups, membership card types, product types, and service packages.
""",
    'author': 'aitilen',
    'license': 'LGPL-3',
    'depends': [
        'gara_workshop',
    ],
    'data': [
        'security/ir_model_access.xml',
        'data/gara_master_data.xml',
        'views/gara_master_data_views.xml',
        'views/member_card_views.xml',
        'views/res_partner_views.xml',
        'views/care_activity_views.xml',
        'views/data_merge_wizard_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': False,
}
