# -*- coding: utf-8 -*-

from odoo.tests.common import tagged, TransactionCase


@tagged('post_install', '-at_install', 'gara_asset')
class TestGaraAsset(TransactionCase):

    def _account(self, code, name, account_type):
        return self.env['account.account'].create({
            'code': code,
            'name': name,
            'account_type': account_type,
        })

    def _category(self):
        journal = self.env['account.journal'].search([
            ('type', '=', 'general'),
            ('company_id', '=', self.env.company.id),
        ], limit=1)
        if not journal:
            journal = self.env['account.journal'].create({
                'name': 'Asset Journal',
                'code': 'TSA',
                'type': 'general',
                'company_id': self.env.company.id,
            })
        return self.env['gara.asset.category'].create({
            'name': 'Equipment',
            'code': 'EQUIP',
            'asset_account_id': self._account('211900', 'Fixed Asset Test', 'asset_fixed').id,
            'depreciation_account_id': self._account('214900', 'Accumulated Depreciation Test', 'asset_fixed').id,
            'expense_account_id': self._account('642900', 'Depreciation Expense Test', 'expense_depreciation').id,
            'journal_id': journal.id,
            'default_method_number': 4,
            'default_period_months': 1,
        })

    def test_confirm_generates_depreciation_schedule(self):
        category = self._category()
        asset = self.env['gara.asset'].create({
            'name': 'Lift',
            'category_id': category.id,
            'acquisition_date': '2026-04-01',
            'first_depreciation_date': '2026-04-30',
            'original_value': 12000000.0,
            'salvage_value': 2000000.0,
            'method_number': 4,
            'period_months': 1,
        })

        asset.action_confirm()

        self.assertEqual(asset.state, 'running')
        self.assertEqual(len(asset.schedule_ids), 4)
        self.assertEqual(sum(asset.schedule_ids.mapped('amount')), 10000000.0)
        self.assertEqual(asset.schedule_ids[0].depreciation_date.isoformat(), '2026-04-30')
        self.assertEqual(asset.schedule_ids[-1].depreciation_date.isoformat(), '2026-07-30')

    def test_create_depreciation_move(self):
        category = self._category()
        asset = self.env['gara.asset'].create({
            'name': 'Compressor',
            'category_id': category.id,
            'acquisition_date': '2026-04-01',
            'first_depreciation_date': '2026-04-30',
            'original_value': 4000000.0,
            'method_number': 4,
            'period_months': 1,
        })
        asset.action_confirm()
        line = asset.schedule_ids[0]

        line.action_create_move()

        self.assertTrue(line.move_id)
        self.assertEqual(line.move_id.state, 'draft')
        self.assertEqual(line.move_id.gara_asset_id, asset)
        self.assertEqual(sum(line.move_id.line_ids.mapped('debit')), line.amount)
        self.assertEqual(sum(line.move_id.line_ids.mapped('credit')), line.amount)
