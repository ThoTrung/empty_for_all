# -*- coding: utf-8 -*-
{
    'name': "Luxboat",
    'version': '17.0.1.0.0',
    'summary': "Luxboat to luxboat",
    'description': """""",
    'author': "trungtho6789@gmail.com",
    'website': "https://www.linhha.com",
    'category': 'luxboat',

    'depends': [
        'base',
        'web',
        'website',
        'website_sale',
        'website_blog',
    ],
    'sequence': -100,
    # always loaded
    'data': [
        'security/ir.model.access.csv',
        # 'views/views.xml',
        # 'views/templates.xml',
        'views/templates_replace_odoo_default.xml',

        'views/blog_post_view.xml',

        # Don't need to choose Font from here.
        # Static snippet
        'views/static_template.xml',
        # 'views/snippet_options.xml',
        'views/dynamic_snippet_templates.xml',
        'views/news_template.xml',
        'views/daily_tour_template.xml',
        'views/boat_rental_template.xml',
        'views/luxboat_destination_template.xml',
        'views/gallery_template.xml',

        'views/snippet_header_container.xml',
        'views/website_snippet_filters.xml',

        # Modal
        # 'views/modal_templates.xml',
        'views/website_popup_templates.xml',
        'views/website_popup_view.xml',

        'views/website_menu.xml',
        # 'views/snippet_dynamic_products.xml',
        #
        # 'views/snippets.xml',

    ],
    "assets": {
        "web.assets_frontend": [
            "luxboat/static/src/scss/website_font.scss",
            "luxboat/static/src/scss/styles.scss",
            # JS
            "luxboat/static/src/js/website_popup.js",
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}

