# -*- coding: utf-8 -*-
{
    'name': 'Zgara Payroll KPI',
    'version': '17.0.1.0.0',
    'category': 'Human Resources',
    'summary': 'KGara-style payroll, attendance and KPI foundation',
    'description': """
Adds lightweight KGara-style HR payroll and KPI catalogs without depending on
enterprise payroll: salary minimums, grades, allowances, bonus/penalty,
attendance summaries, KPI templates and employee KPI assignments.
""",
    'author': 'aitilen',
    'license': 'LGPL-3',
    'depends': [
        'gara_workshop',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/pit_data.xml',
        'views/payroll_kpi_views.xml',
        'views/hr_shift_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': False,
}
