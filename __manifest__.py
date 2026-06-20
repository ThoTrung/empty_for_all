# -*- coding: utf-8 -*-
{
    "name": "Spa Zalo OA (ZNS)",
    "version": "17.0.1.0.0",
    "category": "Services",
    "summary": "Gửi tin Zalo tự động cho khách hàng qua ZNS (nhắc lịch, ...)",
    "author": "Trung Tho",
    "license": "LGPL-3",
    "depends": [
        "booking_calendar",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_config_parameter_data.xml",
        "data/cron.xml",
        "views/spa_zalo_oa_account_views.xml",
        "views/spa_zalo_message_views.xml",
        "views/res_config_settings_views.xml",
        "views/menu.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
