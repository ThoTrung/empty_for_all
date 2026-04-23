# -*- coding: utf-8 -*-

import base64

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import tagged, TransactionCase
from odoo.tools.safe_eval import safe_eval


@tagged('post_install', '-at_install', 'gara_accounting_ops')
class TestGaraAccountingOps(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.journal = cls.env['account.journal'].search([
            ('company_id', '=', cls.env.company.id),
            ('type', '=', 'general'),
        ], limit=1)
        if not cls.journal:
            cls.journal = cls.env['account.journal'].create({
                'name': 'Gara Test Journal',
                'code': 'GTJ',
                'type': 'general',
                'company_id': cls.env.company.id,
            })

    def _create_move(self, group, reason):
        return self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': self.journal.id,
            'date': fields.Date.today(),
            'gara_document_group_id': group.id,
            'gara_document_reason_id': reason.id,
            'gara_document_note': 'Test document metadata',
        })

    def _create_account(self, code, name, account_type='expense'):
        existing = self.env['account.account'].search([
            ('company_id', '=', self.env.company.id),
            ('code', '=', code),
        ], limit=1)
        if existing:
            return existing
        return self.env['account.account'].create({
            'name': name,
            'code': code,
            'account_type': account_type,
            'company_id': self.env.company.id,
        })

    def test_seeded_document_reason_belongs_to_group(self):
        group = self.env.ref('gara_accounting_ops.document_group_receipt')
        reason = self.env.ref('gara_accounting_ops.document_reason_service_payment')

        self.assertEqual(reason.group_id, group)
        self.assertEqual(group.default_reason_id, reason)

    def test_account_move_accepts_matching_document_reason(self):
        group = self.env.ref('gara_accounting_ops.document_group_receipt')
        reason = self.env.ref('gara_accounting_ops.document_reason_service_payment')

        move = self._create_move(group, reason)

        self.assertEqual(move.gara_document_group_id, group)
        self.assertEqual(move.gara_document_reason_id, reason)
        self.assertEqual(move.gara_document_note, 'Test document metadata')

    def test_account_move_rejects_mismatched_document_reason(self):
        group = self.env.ref('gara_accounting_ops.document_group_receipt')
        reason = self.env.ref('gara_accounting_ops.document_reason_supplier_payment')

        with self.assertRaises(ValidationError):
            self._create_move(group, reason)

    def test_csv_invoice_import_creates_draft_invoice(self):
        product = self.env['product.product'].create({
            'name': 'Imported Service',
            'type': 'service',
            'lst_price': 150.0,
        })
        payload = (
            "invoice_ref,partner,invoice_date,product,description,quantity,price_unit\n"
            "INV-IMPORT-1,Imported Customer,2026-04-22,%s,Labour,2,150\n"
            "INV-IMPORT-1,Imported Customer,2026-04-22,%s,Parts,1,50\n"
        ) % (product.name, product.name)
        group = self.env.ref('gara_accounting_ops.document_group_sale_invoice')
        reason = self.env.ref('gara_accounting_ops.document_reason_service_invoice')
        wizard = self.env['gara.invoice.import.wizard'].create({
            'company_id': self.env.company.id,
            'move_type': 'out_invoice',
            'gara_document_group_id': group.id,
            'gara_document_reason_id': reason.id,
            'file_name': 'invoice_import.csv',
            'file_data': base64.b64encode(payload.encode('utf-8')),
        })

        wizard.action_import()

        move = self.env['account.move'].search([
            ('ref', '=', 'INV-IMPORT-1'),
            ('move_type', '=', 'out_invoice'),
        ], limit=1)
        self.assertTrue(move)
        self.assertEqual(move.state, 'draft')
        self.assertEqual(move.partner_id.name, 'Imported Customer')
        self.assertEqual(move.gara_document_group_id, group)
        self.assertEqual(move.gara_document_reason_id, reason)
        self.assertEqual(len(move.invoice_line_ids), 2)
        self.assertEqual(sum(move.invoice_line_ids.mapped('quantity')), 3.0)

    def test_csv_journal_entry_import_creates_balanced_draft_entry(self):
        debit_account = self.env['account.account'].search([
            ('company_id', '=', self.env.company.id),
            ('deprecated', '=', False),
        ], limit=1)
        credit_account = self.env['account.account'].search([
            ('company_id', '=', self.env.company.id),
            ('deprecated', '=', False),
            ('id', '!=', debit_account.id),
        ], limit=1)
        payload = (
            "entry_ref,date,account,label,debit,credit,partner\n"
            "JE-IMPORT-1,2026-04-22,%s,Debit line,100,0,Imported Partner\n"
            "JE-IMPORT-1,2026-04-22,%s,Credit line,0,100,Imported Partner\n"
        ) % (debit_account.code, credit_account.code)
        group = self.env.ref('gara_accounting_ops.document_group_journal')
        reason = self.env.ref('gara_accounting_ops.document_reason_adjustment')
        wizard = self.env['gara.journal.entry.import.wizard'].create({
            'company_id': self.env.company.id,
            'journal_id': self.journal.id,
            'gara_document_group_id': group.id,
            'gara_document_reason_id': reason.id,
            'file_name': 'journal_entry_import.csv',
            'file_data': base64.b64encode(payload.encode('utf-8')),
        })

        wizard.action_import()

        move = self.env['account.move'].search([
            ('ref', '=', 'JE-IMPORT-1'),
            ('move_type', '=', 'entry'),
        ], limit=1)
        self.assertTrue(move)
        self.assertEqual(move.state, 'draft')
        self.assertEqual(move.gara_document_group_id, group)
        self.assertEqual(move.gara_document_reason_id, reason)
        self.assertEqual(len(move.line_ids), 2)
        self.assertEqual(sum(move.line_ids.mapped('debit')), 100.0)
        self.assertEqual(sum(move.line_ids.mapped('credit')), 100.0)

    def test_csv_journal_entry_import_rejects_unbalanced_entry(self):
        debit_account = self.env['account.account'].search([
            ('company_id', '=', self.env.company.id),
            ('deprecated', '=', False),
        ], limit=1)
        credit_account = self.env['account.account'].search([
            ('company_id', '=', self.env.company.id),
            ('deprecated', '=', False),
            ('id', '!=', debit_account.id),
        ], limit=1)
        payload = (
            "entry_ref,account,debit,credit\n"
            "JE-BAD-IMPORT,%s,100,0\n"
            "JE-BAD-IMPORT,%s,0,90\n"
        ) % (debit_account.code, credit_account.code)
        wizard = self.env['gara.journal.entry.import.wizard'].create({
            'company_id': self.env.company.id,
            'journal_id': self.journal.id,
            'file_name': 'journal_entry_import.csv',
            'file_data': base64.b64encode(payload.encode('utf-8')),
        })

        with self.assertRaises(UserError):
            wizard.action_import()

    def test_closing_lock_wizard_updates_period_lock_date(self):
        original_period = self.env.company.period_lock_date
        wizard = self.env['gara.closing.lock.wizard'].create({
            'company_id': self.env.company.id,
            'period_lock_date': '2026-03-31',
            'allow_backward': True,
            'note': 'Test lock',
        })

        wizard.action_apply()

        self.assertEqual(
            self.env.company.period_lock_date,
            fields.Date.to_date('2026-03-31'),
        )
        self.env.company.period_lock_date = original_period

    def test_opening_balance_wizard_creates_draft_entry(self):
        debit_account = self.env['account.account'].search([
            ('company_id', '=', self.env.company.id),
            ('deprecated', '=', False),
        ], limit=1)
        credit_account = self.env['account.account'].search([
            ('company_id', '=', self.env.company.id),
            ('deprecated', '=', False),
            ('id', '!=', debit_account.id),
        ], limit=1)
        wizard = self.env['gara.opening.balance.wizard'].create({
            'company_id': self.env.company.id,
            'journal_id': self.journal.id,
            'date': '2026-01-01',
            'ref': 'Opening test',
            'line_ids': [
                (0, 0, {'account_id': debit_account.id, 'debit': 50.0, 'name': 'Opening debit'}),
                (0, 0, {'account_id': credit_account.id, 'credit': 50.0, 'name': 'Opening credit'}),
            ],
        })

        action = wizard.action_create_move()
        move = self.env['account.move'].browse(action['res_id'])

        self.assertEqual(move.ref, 'Opening test')
        self.assertEqual(move.state, 'draft')
        self.assertEqual(sum(move.line_ids.mapped('debit')), 50.0)
        self.assertEqual(sum(move.line_ids.mapped('credit')), 50.0)

    def test_closing_config_can_store_mapping(self):
        account = self.env['account.account'].search([
            ('company_id', '=', self.env.company.id),
            ('deprecated', '=', False),
        ], limit=1)
        config = self.env['gara.closing.config'].create({
            'name': 'Close income',
            'journal_id': self.journal.id,
            'destination_account_id': account.id,
            'source_account_ids': [(6, 0, [account.id])],
        })

        self.assertEqual(config.source_account_ids, account)

    def test_document_renumber_wizard_updates_draft_moves(self):
        move = self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': self.journal.id,
            'date': '2026-04-01',
        })
        wizard = self.env['gara.document.renumber.wizard'].create({
            'company_id': self.env.company.id,
            'journal_id': self.journal.id,
            'date_from': '2026-04-01',
            'date_to': '2026-04-30',
            'prefix': 'TEST/',
            'padding': 3,
            'next_number': 7,
        })

        wizard.action_apply()

        self.assertEqual(move.name, 'TEST/007')

    def test_product_cost_recompute_wizard_can_apply_preview_cost(self):
        product = self.env['product.product'].create({
            'name': 'Costed Product',
            'type': 'consu',
        })
        wizard = self.env['gara.product.cost.recompute.wizard'].create({
            'company_id': self.env.company.id,
            'product_ids': [(6, 0, [product.id])],
            'method': 'current_standard',
        })
        wizard.action_compute()
        wizard.line_ids.new_cost = 123.0

        wizard.action_apply()

        self.assertEqual(product.standard_price, 123.0)

    def test_allocation_plan_can_create_draft_allocation_entry(self):
        source_account = self._create_account('P40101', 'P4 Source Expense')
        dest_a = self._create_account('P40102', 'P4 Destination A')
        dest_b = self._create_account('P40103', 'P4 Destination B')
        clearing = self._create_account('P40104', 'P4 Clearing Income', 'income')
        source_move = self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': self.journal.id,
            'date': '2026-04-10',
            'ref': 'P4 allocation source',
            'line_ids': [
                (0, 0, {
                    'name': 'Source debit',
                    'account_id': source_account.id,
                    'debit': 1000.0,
                }),
                (0, 0, {
                    'name': 'Clearing credit',
                    'account_id': clearing.id,
                    'credit': 1000.0,
                }),
            ],
        })
        source_move.action_post()
        plan = self.env['gara.allocation.plan'].create({
            'name': 'P4 overhead allocation',
            'company_id': self.env.company.id,
            'journal_id': self.journal.id,
            'source_account_id': source_account.id,
            'method': 'percent',
            'line_ids': [
                (0, 0, {
                    'name': 'Service A',
                    'destination_account_id': dest_a.id,
                    'percent': 60.0,
                }),
                (0, 0, {
                    'name': 'Service B',
                    'destination_account_id': dest_b.id,
                    'percent': 40.0,
                }),
            ],
        })
        wizard = self.env['gara.allocation.run.wizard'].create({
            'plan_id': plan.id,
            'company_id': self.env.company.id,
            'date_from': '2026-04-01',
            'date_to': '2026-04-30',
            'date': '2026-04-30',
            'ref': 'P4 allocation run',
        })

        wizard.action_prepare_lines()
        action = wizard.action_create_move()
        execution = self.env['gara.allocation.execution'].browse(action['res_id'])
        move = execution.move_id

        self.assertEqual(execution.amount, 1000.0)
        self.assertEqual(len(execution.line_ids), 2)
        self.assertEqual(move.state, 'draft')
        self.assertEqual(sum(move.line_ids.mapped('debit')), 1000.0)
        self.assertEqual(sum(move.line_ids.mapped('credit')), 1000.0)
        self.assertEqual(
            move.line_ids.filtered(lambda line: line.account_id == source_account).credit,
            1000.0,
        )

    def test_period_rollover_wizard_creates_opening_entry(self):
        receivable = self._create_account('P40901', 'P4 Receivable', 'asset_receivable')
        liability = self._create_account('P40902', 'P4 Liability', 'liability_current')
        if 'include_initial_balance' in receivable._fields:
            receivable.include_initial_balance = True
            liability.include_initial_balance = True
        partner_a = self.env['res.partner'].create({'name': 'Rollover Partner A'})
        partner_b = self.env['res.partner'].create({'name': 'Rollover Partner B'})
        for partner, amount, date in (
            (partner_a, 120.0, '2025-12-20'),
            (partner_b, 80.0, '2025-12-21'),
        ):
            move = self.env['account.move'].create({
                'move_type': 'entry',
                'journal_id': self.journal.id,
                'date': date,
                'line_ids': [
                    (0, 0, {
                        'name': 'Receivable',
                        'account_id': receivable.id,
                        'partner_id': partner.id,
                        'debit': amount,
                    }),
                    (0, 0, {
                        'name': 'Liability',
                        'account_id': liability.id,
                        'credit': amount,
                    }),
                ],
            })
            move.action_post()
        original_period_lock = self.env.company.period_lock_date
        wizard = self.env['gara.period.rollover.wizard'].create({
            'company_id': self.env.company.id,
            'journal_id': self.journal.id,
            'closing_date': '2025-12-31',
            'opening_date': '2026-01-01',
            'include_partner_details': True,
            'lock_previous_period': True,
            'ref': 'P4 rollover',
        })

        wizard.action_prepare_lines()
        receivable_lines = wizard.line_ids.filtered(lambda line: line.account_id == receivable and line.partner_id)
        self.assertEqual(len(receivable_lines), 2)
        self.assertEqual(sum(receivable_lines.mapped('debit')), 200.0)
        liability_lines = wizard.line_ids.filtered(lambda line: line.account_id == liability)
        self.assertEqual(sum(liability_lines.mapped('credit')), 200.0)

        action = wizard.action_create_move()
        move = self.env['account.move'].browse(action['res_id'])
        move_receivable = move.line_ids.filtered(lambda line: line.account_id == receivable and line.partner_id)
        self.assertEqual(move.date, fields.Date.to_date('2026-01-01'))
        self.assertEqual(sum(move_receivable.mapped('debit')), 200.0)
        self.assertEqual(self.env.company.period_lock_date, fields.Date.to_date('2025-12-31'))
        self.env.company.period_lock_date = original_period_lock

    def test_default_document_parameters_apply_on_create(self):
        company = self.env.company
        company.write({
            'gara_enable_document_auto_defaults': True,
            'gara_enable_document_numbering': True,
            'gara_document_number_prefix': 'PKT/%(year)s/',
            'gara_document_number_padding': 3,
            'gara_document_number_next': 7,
            'gara_document_number_sync_ref': True,
            'gara_default_journal_group_id': self.env.ref('gara_accounting_ops.document_group_journal').id,
            'gara_default_journal_reason_id': self.env.ref('gara_accounting_ops.document_reason_adjustment').id,
        })

        move = self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': self.journal.id,
            'date': '2026-04-01',
        })

        self.assertEqual(move.gara_document_group_id.code, 'PKT')
        self.assertEqual(move.gara_document_reason_id.code, 'DIEU_CHINH')
        self.assertEqual(move.gara_document_number, 'PKT/2026/007')
        self.assertEqual(move.ref, 'PKT/2026/007')

    def test_document_sequence_rule_resets_yearly(self):
        company = self.env.company
        company.write({
            'gara_enable_document_numbering': True,
            'gara_document_number_sync_ref': False,
        })
        group = self.env.ref('gara_accounting_ops.document_group_journal')
        self.env['gara.document.sequence.rule'].create({
            'name': 'Journal yearly sequence',
            'company_id': company.id,
            'move_type': 'entry',
            'document_group_id': group.id,
            'prefix': 'SEQ/%(year)s/',
            'padding': 2,
            'number_next': 55,
            'reset_yearly': True,
            'current_year': 2025,
        })

        move = self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': self.journal.id,
            'date': '2026-01-02',
            'gara_document_group_id': group.id,
        })
        rule = self.env['gara.document.sequence.rule'].search([
            ('company_id', '=', company.id),
            ('move_type', '=', 'entry'),
            ('document_group_id', '=', group.id),
        ], limit=1)

        self.assertEqual(move.gara_document_number, 'SEQ/2026/01')
        self.assertEqual(rule.current_year, 2026)
        self.assertEqual(rule.number_next, 2)

    def test_accounting_rule_engine_maps_journal_and_line_account(self):
        company = self.env.company
        company.gara_enable_accounting_rule_engine = True
        sale_journal = self.env['account.journal'].search([
            ('company_id', '=', company.id),
            ('type', '=', 'sale'),
        ], limit=1)
        target_sale_journal = self.env['account.journal'].create({
            'name': 'Rule Sale Journal',
            'code': 'RSJ',
            'type': 'sale',
            'company_id': company.id,
        })
        income_vat = self._create_account('P40910', 'P4 VAT Income', 'income')
        income_non_vat = self._create_account('P40911', 'P4 Non VAT Income', 'income')
        self.env['gara.accounting.rule'].create({
            'name': 'VAT service invoice',
            'company_id': company.id,
            'sequence': 1,
            'move_type': 'out_invoice',
            'business_type': 'service',
            'partner_scope': 'customer',
            'payment_channel': 'bank',
            'tax_scope': 'vat',
            'output_journal_id': target_sale_journal.id,
            'output_document_group_id': self.env.ref('gara_accounting_ops.document_group_sale_invoice').id,
            'output_document_reason_id': self.env.ref('gara_accounting_ops.document_reason_service_invoice').id,
            'output_income_account_id': income_vat.id,
        })
        self.env['gara.accounting.rule'].create({
            'name': 'Non VAT service invoice',
            'company_id': company.id,
            'sequence': 2,
            'move_type': 'out_invoice',
            'business_type': 'service',
            'partner_scope': 'customer',
            'payment_channel': 'bank',
            'tax_scope': 'non_vat',
            'output_journal_id': target_sale_journal.id,
            'output_income_account_id': income_non_vat.id,
        })
        tax = company.account_sale_tax_id or self.env['account.tax'].search([
            ('company_id', '=', company.id),
            ('type_tax_use', '=', 'sale'),
        ], limit=1)
        if not tax:
            tax = self.env['account.tax'].create({
                'name': 'VAT 10%',
                'amount_type': 'percent',
                'amount': 10.0,
                'type_tax_use': 'sale',
                'company_id': company.id,
            })
        partner = self.env['res.partner'].create({'name': 'Rule Customer'})
        product = self.env['product.product'].create({
            'name': 'Rule Product',
            'type': 'service',
        })
        move = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'journal_id': sale_journal.id,
            'partner_id': partner.id,
            'invoice_date': '2026-05-02',
            'gara_business_type': 'service',
            'gara_payment_channel': 'bank',
            'invoice_line_ids': [
                (0, 0, {
                    'product_id': product.id,
                    'name': 'Rule line',
                    'quantity': 1.0,
                    'price_unit': 100.0,
                    'tax_ids': [(6, 0, tax.ids)] if tax else False,
                }),
            ],
        })
        move.action_gara_apply_accounting_policy()

        self.assertEqual(move.gara_tax_scope, 'vat')
        self.assertEqual(move.journal_id, target_sale_journal)
        self.assertEqual(move.gara_accounting_rule_id.name, 'VAT service invoice')
        self.assertEqual(move.invoice_line_ids.account_id, income_vat)

    def test_document_actions_have_expected_defaults(self):
        mapping = [
            (
                'gara_accounting_ops.action_gara_receipt_documents',
                'PT',
                'entry',
                'gara_accounting_ops.document_group_receipt',
            ),
            (
                'gara_accounting_ops.action_gara_payment_documents',
                'PC',
                'entry',
                'gara_accounting_ops.document_group_payment',
            ),
            (
                'gara_accounting_ops.action_gara_sale_invoice_documents',
                'HDBH',
                'out_invoice',
                'gara_accounting_ops.document_group_sale_invoice',
            ),
            (
                'gara_accounting_ops.action_gara_purchase_invoice_documents',
                'HDMH',
                'in_invoice',
                'gara_accounting_ops.document_group_purchase_invoice',
            ),
            (
                'gara_accounting_ops.action_gara_journal_documents',
                'PKT',
                'entry',
                'gara_accounting_ops.document_group_journal',
            ),
        ]

        for action_xmlid, expected_code, expected_move_type, expected_group_xmlid in mapping:
            action = self.env.ref(action_xmlid)
            self.assertIn("gara_document_group_id.code", action.domain)
            self.assertIn(expected_code, action.domain)
            ctx = safe_eval(action.context or '{}')
            self.assertEqual(ctx.get('default_move_type'), expected_move_type)
            self.assertEqual(
                ctx.get('default_gara_document_group_id'),
                self.env.ref(expected_group_xmlid).id,
            )
