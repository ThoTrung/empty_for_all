# -*- coding: utf-8 -*-

from odoo.tests.common import tagged, TransactionCase


@tagged('post_install', '-at_install', 'gara_costing')
class TestGaraCosting(TransactionCase):

    def test_norm_and_production_cost_flow(self):
        product = self.env['product.product'].create({
            'name': 'Finished Service Bundle',
            'type': 'consu',
        })
        material = self.env['gara.cost.element'].create({
            'name': 'Material',
            'code': 'MAT',
            'element_type': 'material',
        })
        norm = self.env['gara.product.norm'].create({
            'name': 'Standard bundle norm',
            'product_tmpl_id': product.product_tmpl_id.id,
            'line_ids': [(0, 0, {
                'cost_element_id': material.id,
                'description': 'Parts',
                'quantity': 2.0,
                'price_unit': 100.0,
            })],
        })

        self.assertEqual(norm.planned_cost, 200.0)

        order = self.env['gara.production.order'].create({
            'product_id': product.id,
            'norm_id': norm.id,
            'quantity_planned': 3.0,
        })
        order.action_confirm()

        self.assertEqual(order.state, 'confirmed')
        self.assertEqual(order.planned_cost, 600.0)
        self.assertEqual(order.actual_cost, 600.0)

        order.quantity_done = 3.0
        order.action_done()
        self.assertEqual(order.state, 'done')
        self.assertEqual(order.unit_actual_cost, 200.0)

    def test_wip_opening_can_store_balance(self):
        product = self.env['product.product'].create({
            'name': 'WIP Product',
            'type': 'consu',
        })
        opening = self.env['gara.wip.opening'].create({
            'name': 'Opening WIP',
            'product_id': product.id,
            'quantity': 1.0,
            'amount': 500.0,
        })

        self.assertEqual(opening.amount, 500.0)
