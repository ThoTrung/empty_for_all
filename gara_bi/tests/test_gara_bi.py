# -*- coding: utf-8 -*-

from odoo.tests.common import tagged, TransactionCase


@tagged('post_install', '-at_install', 'gara_bi')
class TestGaraBi(TransactionCase):

    def test_monthly_kpi_report_is_queryable(self):
        self.env['gara.bi.monthly.kpi'].search([], limit=1)

    def test_monthly_kpi_includes_workshop_case(self):
        partner = self.env['res.partner'].create({'name': 'BI Customer'})
        case = self.env['gara.workshop.case'].create({
            'partner_id': partner.id,
            'user_id': self.env.user.id,
        })

        report = self.env['gara.bi.monthly.kpi'].search([
            ('report_date', '=', case.intake_date.date().replace(day=1)),
            ('company_id', '=', case.company_id.id),
        ], limit=1)

        self.assertTrue(report)
        self.assertGreaterEqual(report.case_count, 1)

    def test_management_summary_is_queryable_and_computes_rates(self):
        partner = self.env['res.partner'].create({'name': 'BI Management Customer'})
        case = self.env['gara.workshop.case'].create({
            'partner_id': partner.id,
            'user_id': self.env.user.id,
        })

        report = self.env['gara.bi.management.summary'].search([
            ('report_date', '=', case.intake_date.date().replace(day=1)),
            ('company_id', '=', case.company_id.id),
        ], limit=1)

        self.assertTrue(report)
        self.assertGreaterEqual(report.case_count, 1)
        self.assertGreaterEqual(report.open_case_count, 1)
        self.assertGreaterEqual(report.collection_rate, 0.0)
        self.assertGreaterEqual(report.close_rate, 0.0)
