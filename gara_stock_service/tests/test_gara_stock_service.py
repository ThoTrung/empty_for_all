# -*- coding: utf-8 -*-

from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import tagged, TransactionCase


@tagged('post_install', '-at_install', 'gara_stock_service')
class TestGaraStockService(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.warehouse = cls.env['stock.warehouse'].search([
            ('company_id', '=', cls.company.id),
        ], limit=1)
        if not cls.warehouse:
            cls.warehouse = cls.env['stock.warehouse'].create({
                'name': 'Test Warehouse',
                'code': 'TWH',
                'company_id': cls.company.id,
            })
        cls.partner = cls.env['res.partner'].create({'name': 'Stock Service Customer'})
        cls.case = cls.env['gara.workshop.case'].create({
            'partner_id': cls.partner.id,
            'company_id': cls.company.id,
        })
        cls.product = cls.env['product.product'].create({
            'name': 'Brake Pad Test',
            'type': 'product',
        })

    def _create_request(self):
        return self.env['gara.service.stock.request'].create({
            'case_id': self.case.id,
            'company_id': self.company.id,
            'warehouse_id': self.warehouse.id,
            'picking_type_id': self.warehouse.out_type_id.id,
            'location_id': self.warehouse.lot_stock_id.id,
            'location_dest_id': self.env.ref('stock.stock_location_customers').id,
            'line_ids': [(0, 0, {
                'product_id': self.product.id,
                'name': self.product.display_name,
                'product_uom_qty': 2.0,
                'product_uom': self.product.uom_id.id,
            })],
        })

    def test_create_picking_from_service_stock_request(self):
        request = self._create_request()

        request.action_confirm()
        self.assertEqual(request.state, 'confirmed')

        request.action_create_picking()
        self.assertEqual(request.state, 'picking')
        self.assertTrue(request.picking_id)
        self.assertEqual(request.picking_id.gara_service_stock_request_id, request)
        self.assertEqual(request.picking_id.origin, request.name)
        self.assertEqual(request.picking_id.partner_id, self.partner)
        self.assertEqual(request.picking_id.move_ids.product_id, self.product)
        self.assertEqual(request.picking_id.move_ids.product_uom_qty, 2.0)

    def test_request_requires_lines(self):
        request = self.env['gara.service.stock.request'].create({
            'case_id': self.case.id,
            'company_id': self.company.id,
            'warehouse_id': self.warehouse.id,
            'picking_type_id': self.warehouse.out_type_id.id,
            'location_id': self.warehouse.lot_stock_id.id,
            'location_dest_id': self.env.ref('stock.stock_location_customers').id,
        })

        with self.assertRaises(UserError):
            request.action_confirm()

    def test_line_quantity_must_be_positive(self):
        with self.assertRaises(ValidationError):
            self.env['gara.service.stock.request.line'].create({
                'request_id': self._create_request().id,
                'product_id': self.product.id,
                'name': self.product.display_name,
                'product_uom_qty': 0.0,
                'product_uom': self.product.uom_id.id,
            })

    def test_inventory_batch_tracks_count_difference(self):
        self.env['stock.quant']._update_available_quantity(
            self.product,
            self.warehouse.lot_stock_id,
            5.0,
        )
        batch = self.env['gara.stock.inventory.batch'].create({
            'company_id': self.company.id,
            'warehouse_id': self.warehouse.id,
            'location_id': self.warehouse.lot_stock_id.id,
            'line_ids': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_id': self.product.uom_id.id,
                'counted_qty': 3.0,
            })],
        })

        batch.action_confirm()
        self.assertEqual(batch.state, 'confirmed')
        self.assertEqual(batch.line_ids.theoretical_qty, 5.0)
        self.assertEqual(batch.line_ids.difference_qty, -2.0)
        self.assertEqual(batch.difference_line_count, 1)

        batch.action_done()
        self.assertEqual(batch.state, 'done')

    def test_inventory_counted_quantity_must_not_be_negative(self):
        with self.assertRaises(ValidationError):
            self.env['gara.stock.inventory.batch'].create({
                'company_id': self.company.id,
                'warehouse_id': self.warehouse.id,
                'location_id': self.warehouse.lot_stock_id.id,
                'line_ids': [(0, 0, {
                    'product_id': self.product.id,
                    'product_uom_id': self.product.uom_id.id,
                    'counted_qty': -1.0,
                })],
            })

    def test_gara_min_qty_search_finds_low_stock_product(self):
        tmpl = self.product.product_tmpl_id
        tmpl.gara_min_qty = 10.0
        self.env['stock.quant']._update_available_quantity(
            self.product,
            self.warehouse.lot_stock_id,
            4.0,
        )

        products = self.env['product.template'].search([
            ('gara_below_min_qty', '=', True),
        ])

        self.assertIn(tmpl, products)

    def test_stock_opening_wizard_updates_quantity_and_cost(self):
        self.env['stock.quant']._update_available_quantity(
            self.product,
            self.warehouse.lot_stock_id,
            2.0,
        )
        wizard = self.env['gara.stock.opening.wizard'].create({
            'company_id': self.company.id,
            'opening_date': '2026-01-01',
            'location_id': self.warehouse.lot_stock_id.id,
            'set_standard_cost': True,
            'line_ids': [(0, 0, {
                'product_id': self.product.id,
                'current_qty': 2.0,
                'opening_qty': 5.0,
                'unit_cost': 55.0,
            })],
        })

        wizard.action_apply()

        qty = self.env['stock.quant']._get_available_quantity(
            self.product,
            self.warehouse.lot_stock_id,
            allow_negative=True,
        )
        self.assertEqual(qty, 5.0)
        self.assertEqual(self.product.standard_price, 55.0)
