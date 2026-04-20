# -*- coding: utf-8 -*-
{
    'name': 'Rental',
    'version': '17.0.1.0.18',
    'category': 'Rental',
    'summary': 'Rental service module.',
    'author': "Nguyễn Trung Thọ",

    # any module necessary for this one to work correctly
    'depends': [
        'base',
        'web',
        'stock',
        'sale',
        'sale_management',
    ],
    'sequence': -100,
    'data': [
        'security/custom_security_groups.xml',
        'security/ir_model_access.xml',
        'security/ir_rule.xml',
        'wizard/create_invoice_wizard.xml',
        'wizard/rental_transport_matrix_overlap_wizard.xml',
        'wizard/reject_confirm_wizard.xml',
        'wizard/link_child_contact_wizard.xml',

        'data/sequence.xml',

        'views/views.xml',
        'views/templates.xml',

        'views/rental_contract_view.xml',
        'views/rental_transport_matrix_view.xml',
        'views/rental_invoice_view.xml',
        'views/res_partner_view.xml',
        'views/res_partner_rental_contract_quick_form.xml',
        'views/res_users_view.xml',
        'views/product_template_view.xml',
        'views/construction_extra_view.xml',
        'views/rental_template_view.xml',
        'views/rental_product_template_set_view.xml',
        'views/product_product_view.xml',
        'views/sale_order_views.xml',
        'views/product_template_attribute_value_view.xml',
        'views/product_attribute_view.xml',
        'views/transport_view.xml',
        'views/transport_truck_view.xml',
        'views/construction_work_view.xml',

        'reports/quotation_price_report.xml',
        'data/quotation_price_report_action.xml',


        'views/account_move_view.xml',

        'views/menu.xml',
    ],
    'assets': {
        'web.assets_frontend': [],
        'web.assets_backend': [
            'rental/static/src/scss/style.scss',
            'rental/static/src/scss/rental_modal.scss',
            'rental/static/src/js/big_modal_dialog.js',
            'rental/static/src/js/download_and_close.js',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}

