# -*- coding: utf-8 -*-

from odoo.tests.common import tagged, TransactionCase


@tagged('post_install', '-at_install', 'gara_warranty_portal')
class TestGaraWarrantyPortal(TransactionCase):

    def test_lookup_wizard_returns_claim_domain(self):
        claim = self.env['gara.warranty.claim'].create({
            'name': 'WCL-LOOKUP',
            'serial_number': 'SN-123',
            'warranty_end_date': '2027-01-01',
        })
        wizard = self.env['gara.warranty.lookup.wizard'].create({
            'query': 'SN-123',
            'state': 'active',
        })

        action = wizard.action_lookup()
        found = self.env['gara.warranty.claim'].search(action['domain'])

        self.assertIn(claim, found)
