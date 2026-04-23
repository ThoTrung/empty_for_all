# -*- coding: utf-8 -*-

from odoo.exceptions import ValidationError
from odoo.exceptions import UserError
from odoo.tests.common import tagged, TransactionCase


@tagged('post_install', '-at_install', 'gara_master_data')
class TestGaraMasterData(TransactionCase):

    def test_partner_classification_fields(self):
        source = self.env.ref('gara_master_data.customer_source_referral')
        status = self.env.ref('gara_master_data.customer_status_active')
        customer_type = self.env.ref('gara_master_data.customer_type_personal')
        membership = self.env.ref('gara_master_data.membership_vip')

        partner = self.env['res.partner'].create({
            'name': 'Master Data Customer',
            'gara_customer_source_id': source.id,
            'gara_customer_status_id': status.id,
            'gara_customer_type_id': customer_type.id,
            'gara_membership_type_id': membership.id,
        })

        self.assertEqual(partner.gara_customer_source_id, source)
        self.assertEqual(partner.gara_customer_status_id, status)
        self.assertEqual(partner.gara_customer_type_id, customer_type)
        self.assertEqual(partner.gara_membership_type_id, membership)

    def test_membership_discount_validation(self):
        with self.assertRaises(ValidationError):
            self.env['gara.membership.type'].create({
                'name': 'Invalid discount',
                'code': 'INVALID_DISCOUNT',
                'discount_percent': 101.0,
            })

    def test_care_result_detail_must_match_result(self):
        partner = self.env['res.partner'].create({'name': 'Care Customer'})
        success = self.env.ref('gara_master_data.care_result_success')
        callback = self.env.ref('gara_master_data.care_result_callback')
        detail = self.env.ref('gara_master_data.care_result_detail_satisfied')

        activity = self.env['gara.care.activity'].create({
            'name': 'Follow-up',
            'partner_id': partner.id,
            'channel': 'phone',
            'outcome': 'ok',
            'care_type_id': self.env.ref('gara_master_data.care_type_after_service').id,
            'result_id': success.id,
            'result_detail_id': detail.id,
        })
        self.assertEqual(activity.result_detail_id, detail)

        with self.assertRaises(ValidationError):
            activity.write({'result_id': callback.id})

    def test_bank_branch_display_name(self):
        bank = self.env['res.bank'].create({'name': 'Test Bank'})
        branch = self.env['gara.bank.branch'].create({
            'bank_id': bank.id,
            'code': 'HN01',
            'name': 'Hanoi Branch',
        })

        self.assertIn('Test Bank', branch.display_name)
        self.assertIn('Hanoi Branch', branch.display_name)
        self.assertIn('HN01', branch.display_name)

    def test_kgara_extra_catalogs(self):
        bank = self.env['res.bank'].create({'name': 'Master Bank'})
        branch = self.env['gara.bank.branch'].create({
            'bank_id': bank.id,
            'code': 'MAIN',
            'name': 'Main Branch',
        })
        bank_account = self.env['gara.bank.account'].create({
            'name': 'Primary bank account',
            'code': 'PRIMARY_BANK',
            'bank_id': bank.id,
            'branch_id': branch.id,
            'account_number': '123456789',
            'account_holder': 'Garage Company',
        })
        payment_method = self.env['gara.payment.method'].create({
            'name': 'Bank transfer',
            'code': 'BANK_TRANSFER',
            'payment_type': 'bank',
        })
        case_type = self.env['gara.case.type'].create({
            'name': 'Repair order',
            'code': 'REPAIR_ORDER',
            'color': 4,
        })
        cost_item = self.env['gara.cost.item'].create({
            'name': 'Parts cost',
            'code': 'PARTS_COST',
            'item_type': 'cost',
        })

        self.assertIn('123456789', bank_account.display_name)
        self.assertEqual(bank_account.branch_id, branch)
        self.assertEqual(payment_method.payment_type, 'bank')
        self.assertEqual(case_type.color, 4)
        self.assertEqual(cost_item.item_type, 'cost')

    def test_product_type_can_classify_product(self):
        product_type = self.env.ref('gara_master_data.product_type_part')
        product = self.env['product.template'].create({
            'name': 'Oil Filter',
            'type': 'consu',
            'gara_product_type_id': product_type.id,
        })

        self.assertEqual(product.gara_product_type_id, product_type)

    def test_service_package_amount_and_line_validation(self):
        labour = self.env['product.product'].create({
            'name': 'Labour',
            'type': 'service',
            'lst_price': 300000.0,
        })
        oil = self.env['product.product'].create({
            'name': 'Engine Oil',
            'type': 'consu',
            'lst_price': 200000.0,
        })

        package = self.env['gara.service.package'].create({
            'name': 'Basic maintenance',
            'code': 'BASIC_MAINT',
            'line_ids': [
                (0, 0, {
                    'product_id': labour.id,
                    'name': labour.display_name,
                    'product_uom_id': labour.uom_id.id,
                    'quantity': 1.0,
                    'price_unit': 300000.0,
                }),
                (0, 0, {
                    'product_id': oil.id,
                    'name': oil.display_name,
                    'product_uom_id': oil.uom_id.id,
                    'quantity': 2.0,
                    'price_unit': 200000.0,
                    'discount': 10.0,
                }),
            ],
        })

        self.assertEqual(package.amount_untaxed, 660000.0)

        with self.assertRaises(ValidationError):
            self.env['gara.service.package.line'].create({
                'package_id': package.id,
                'product_id': labour.id,
                'name': labour.display_name,
                'quantity': 0.0,
                'price_unit': 100000.0,
            })

    def test_partner_merge_wizard_reassigns_core_references(self):
        target = self.env['res.partner'].create({'name': 'Target Customer'})
        source = self.env['res.partner'].create({'name': 'Duplicate Customer'})
        product = self.env['product.product'].create({
            'name': 'Merge Service',
            'type': 'service',
            'lst_price': 100000.0,
        })
        sale_order = self.env['sale.order'].create({
            'partner_id': source.id,
            'order_line': [(0, 0, {
                'product_id': product.id,
                'product_uom_qty': 1.0,
                'price_unit': 100000.0,
            })],
        })

        wizard = self.env['gara.partner.merge.wizard'].create({
            'target_partner_id': target.id,
            'source_partner_ids': [(6, 0, source.ids)],
            'confirm': True,
        })
        wizard.action_merge()

        self.assertEqual(sale_order.partner_id, target)
        self.assertEqual(sale_order.partner_invoice_id, target)
        self.assertFalse(source.active)
        self.assertGreaterEqual(wizard.updated_reference_count, 1)

    def test_product_merge_wizard_reassigns_core_references(self):
        partner = self.env['res.partner'].create({'name': 'Product Merge Customer'})
        target = self.env['product.product'].create({
            'name': 'Target Part',
            'type': 'consu',
            'lst_price': 150000.0,
        })
        source = self.env['product.product'].create({
            'name': 'Duplicate Part',
            'type': 'consu',
            'lst_price': 140000.0,
        })
        sale_order = self.env['sale.order'].create({
            'partner_id': partner.id,
            'order_line': [(0, 0, {
                'product_id': source.id,
                'product_uom_qty': 2.0,
                'price_unit': 140000.0,
            })],
        })

        wizard = self.env['gara.product.merge.wizard'].create({
            'target_product_id': target.id,
            'source_product_ids': [(6, 0, source.ids)],
            'confirm': True,
        })
        wizard.action_merge()

        self.assertEqual(sale_order.order_line.product_id, target)
        self.assertFalse(source.active)
        self.assertGreaterEqual(wizard.updated_reference_count, 1)

    def test_merge_wizards_require_confirmation(self):
        partner = self.env['res.partner'].create({'name': 'Merge Confirm Target'})
        duplicate = self.env['res.partner'].create({'name': 'Merge Confirm Source'})
        wizard = self.env['gara.partner.merge.wizard'].create({
            'target_partner_id': partner.id,
            'source_partner_ids': [(6, 0, duplicate.ids)],
        })

        with self.assertRaises(UserError):
            wizard.action_merge()
