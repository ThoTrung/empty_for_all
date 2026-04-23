# -*- coding: utf-8 -*-
{
    'name': 'Zgara',
    'version': '17.0.1.7.3',
    'category': 'Services/Project',
    'summary': 'Workshop cases, quotations, repairs, payments, CRM care, warranty — Odoo-native integration',
    'description': """
Gara / auto workshop operations on top of Odoo standard apps.

This module implements the **operational core** comparable to Zgara-style systems:
vehicle file (Fleet), service case (job), sale quotation, repair order, customer payment tracking, care activities, warranty claims, and invoice linkage.

**Accounting (this module):** `l10n_vn` (VAS / TT200 chart, VAT, VietQR); customer/vendor invoices & credit notes,
payments, journal items, bank statements; workshop payment register + CSV/XLSX import to `account.payment`;
`gara_case_id` on invoices, payments, journal lines (stored); credit notes inherit case from source invoice;
Settings action to map Gara default products to 5111/5113/632/622 + sale VAT for Vietnam companies.

**Out of scope (use Odoo apps / other modules):** e-invoice providers (MISA/Viettel/VNPT…), TT99-only rules,
payroll, fixed assets, full cost allocation, consolidated multi-company closing.
 """,
    'author': 'aitilen',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
        'contacts',
        'calendar',
        'fleet',
        'sale_management',
        'stock',
        'repair',
        'account',
        'hr',
        'l10n_vn',
    ],
    'data': [
        'security/gara_security.xml',
        'security/ir_model_access.xml',
        'security/gara_rules.xml',
        'data/sequence_data.xml',
        'data/product_data.xml',
        'views/fleet_vehicle_views.xml',
        'views/workshop_dashboard_views.xml',
        'views/workshop_case_views.xml',
        'views/workshop_payment_views.xml',
        'views/care_activity_views.xml',
        'views/warranty_claim_views.xml',
        'views/insurance_claim_views.xml',
        'views/reminder_views.xml',
        'views/survey_views.xml',
        'views/approval_views.xml',
        'views/approval_policy_views.xml',
        'views/assignment_views.xml',
        'views/notification_views.xml',
        'views/audit_log_views.xml',
        'views/member_ledger_views.xml',
        'views/payment_import_wizard_views.xml',
        'views/res_config_settings_views.xml',
        'views/sale_order_views.xml',
        'views/repair_order_views.xml',
        'views/account_move_views.xml',
        'views/account_move_line_views.xml',
        'views/account_payment_views.xml',
        'views/account_catalog_views.xml',
        'data/account_catalog_data.xml',
        'data/gara_menu_actions.xml',
        'views/menu.xml',
    ],
    'demo': [],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': True,
}
