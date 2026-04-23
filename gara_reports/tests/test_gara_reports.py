# -*- coding: utf-8 -*-

from odoo.tests.common import tagged, TransactionCase


@tagged('post_install', '-at_install', 'gara_reports')
class TestGaraReports(TransactionCase):

    def test_service_case_report_includes_workshop_case(self):
        partner = self.env['res.partner'].create({'name': 'Report Customer'})
        case = self.env['gara.workshop.case'].create({
            'partner_id': partner.id,
            'user_id': self.env.user.id,
        })

        report = self.env['gara.service.case.report'].search([
            ('case_id', '=', case.id),
        ], limit=1)

        self.assertTrue(report)
        self.assertEqual(report.partner_id, partner)
        self.assertEqual(report.state, 'draft')

    def test_stock_ledger_report_model_is_queryable(self):
        self.env['gara.stock.ledger.report'].search([], limit=1)

    def test_account_reports_are_queryable(self):
        self.env['gara.account.summary.report'].search([], limit=1)
        self.env['gara.partner.balance.report'].search([], limit=1)
        self.env['gara.bank.cash.report'].search([], limit=1)
        self.env['gara.foreign.currency.report'].search([], limit=1)
        self.env['gara.t.account.report'].search([], limit=1)
        self.env['gara.financial.statement.report'].search([], limit=1)

    def test_product_price_report_includes_product(self):
        template = self.env['product.template'].create({
            'name': 'Report Brake Pad',
            'type': 'consu',
            'list_price': 450000.0,
        })
        product = template.product_variant_id

        report = self.env['gara.product.price.report'].search([
            ('product_id', '=', product.id),
        ], limit=1)

        self.assertTrue(report)
        self.assertEqual(report.product_tmpl_id, product.product_tmpl_id)
        self.assertEqual(report.list_price, 450000.0)

    def test_financial_statement_line_can_map_accounts(self):
        account = self.env['account.account'].search([], limit=1)
        self.assertTrue(account)

        line = self.env['gara.financial.statement.line'].create({
            'name': 'Cash and equivalents',
            'code': 'BCTC_CASH',
            'statement_type': 'balance_sheet',
            'account_ids': [(6, 0, account.ids)],
            'sign': 1,
        })

        self.assertEqual(line.account_ids, account)

    def test_service_case_qweb_report_renders(self):
        partner = self.env['res.partner'].create({'name': 'Printable Customer'})
        case = self.env['gara.workshop.case'].create({
            'partner_id': partner.id,
            'user_id': self.env.user.id,
            'intake_notes': '<p>Printable intake note</p>',
        })

        html, report_type = self.env['ir.actions.report']._render_qweb_html(
            'gara_reports.action_report_gara_service_case',
            case.ids,
        )

        self.assertEqual(report_type, 'html')
        self.assertIn(b'PHIEU TIEP NHAN', html)
        self.assertIn(b'Printable Customer', html)

    def test_workshop_payment_qweb_report_renders(self):
        partner = self.env['res.partner'].create({'name': 'Receipt Customer'})
        case = self.env['gara.workshop.case'].create({
            'partner_id': partner.id,
            'user_id': self.env.user.id,
        })
        payment = self.env['gara.workshop.payment'].create({
            'case_id': case.id,
            'amount': 250000.0,
            'note': 'Dat coc',
        })

        html, report_type = self.env['ir.actions.report']._render_qweb_html(
            'gara_reports.action_report_gara_workshop_payment',
            payment.ids,
        )

        self.assertEqual(report_type, 'html')
        self.assertIn(b'PHIEU THU DICH VU', html)
        self.assertIn(b'Receipt Customer', html)

    def test_account_move_voucher_qweb_report_renders(self):
        journal = self.env['account.journal'].search([
            ('company_id', '=', self.env.company.id),
            ('type', '=', 'general'),
        ], limit=1)
        if not journal:
            journal = self.env['account.journal'].create({
                'name': 'Voucher Journal',
                'code': 'GVJ',
                'type': 'general',
                'company_id': self.env.company.id,
            })

        debit_account = self.env['account.account'].search([
            ('company_id', '=', self.env.company.id),
            ('deprecated', '=', False),
        ], limit=1)
        credit_account = self.env['account.account'].search([
            ('company_id', '=', self.env.company.id),
            ('deprecated', '=', False),
            ('id', '!=', debit_account.id),
        ], limit=1)
        self.assertTrue(debit_account)
        self.assertTrue(credit_account)

        partner = self.env['res.partner'].create({'name': 'Voucher Customer'})
        move = self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': journal.id,
            'date': '2026-04-23',
            'partner_id': partner.id,
            'gara_document_group_id': self.env.ref('gara_accounting_ops.document_group_receipt').id,
            'gara_document_reason_id': self.env.ref('gara_accounting_ops.document_reason_service_payment').id,
            'gara_document_note': 'Voucher test note',
            'line_ids': [
                (0, 0, {
                    'name': 'Thu tien mat',
                    'account_id': debit_account.id,
                    'partner_id': partner.id,
                    'debit': 100000.0,
                    'credit': 0.0,
                }),
                (0, 0, {
                    'name': 'Doanh thu dich vu',
                    'account_id': credit_account.id,
                    'partner_id': partner.id,
                    'debit': 0.0,
                    'credit': 100000.0,
                }),
            ],
        })

        html, report_type = self.env['ir.actions.report']._render_qweb_html(
            'gara_reports.action_report_gara_account_move_voucher',
            move.ids,
        )

        self.assertEqual(report_type, 'html')
        self.assertIn(b'Voucher Customer', html)
        self.assertIn(b'Voucher test note', html)
