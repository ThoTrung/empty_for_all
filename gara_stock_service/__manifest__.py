# -*- coding: utf-8 -*-
{
    'name': 'Zgara Service Stock',
    'version': '17.0.1.0.0',
    'category': 'Inventory/Inventory',
    'summary': 'Service stock requests for Zgara workshop cases',
    'description': """
Adds KGara-style service stock request documents linked to workshop cases.
Each request can generate an Odoo outgoing stock picking for actual inventory
movement and traceability. Adds KGara-style inventory count batches, inventory
difference summaries, and min/max stock thresholds.
""",
    'author': 'aitilen',
    'license': 'LGPL-3',
    'depends': [
        'gara_workshop',
    ],
    'data': [
        'security/ir_model_access.xml',
        'data/sequence_data.xml',
        'views/service_stock_request_views.xml',
        'views/inventory_batch_views.xml',
        'views/stock_opening_wizard_views.xml',
        'views/product_template_views.xml',
        'views/workshop_case_views.xml',
        'views/stock_picking_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': False,
}
