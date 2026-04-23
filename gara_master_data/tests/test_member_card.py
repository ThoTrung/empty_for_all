# -*- coding: utf-8 -*-

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install', 'gara_master_data')
class TestGaraMemberCard(TransactionCase):

    def setUp(self):
        super().setUp()
        self.partner = self.env['res.partner'].create({
            'name': 'Member Card Customer',
            'company_id': self.env.company.id,
        })
        self.membership_vip = self.env.ref('gara_master_data.membership_vip')

    def test_member_card_sequence_sync_and_ledger_link(self):
        card = self.env['gara.member.card'].create({
            'partner_id': self.partner.id,
            'membership_type_id': self.membership_vip.id,
            'state': 'active',
        })
        self.assertTrue(card.name.startswith('MC/'))
        self.assertEqual(self.partner.gara_membership_type_id, self.membership_vip)

        earn_line = self.env['gara.member.ledger'].create({
            'company_id': self.env.company.id,
            'partner_id': self.partner.id,
            'entry_type': 'earn',
            'points': 50.0,
            'state': 'posted',
        })
        redeem_line = self.env['gara.member.ledger'].create({
            'company_id': self.env.company.id,
            'partner_id': self.partner.id,
            'entry_type': 'redeem',
            'points': -20.0,
            'state': 'posted',
        })

        self.assertEqual(earn_line.card_id, card)
        self.assertEqual(redeem_line.card_id, card)
        card.invalidate_recordset()
        self.assertEqual(card.points_earned, 50.0)
        self.assertEqual(card.points_redeemed, 20.0)
        self.assertEqual(card.point_balance, 30.0)

    def test_single_active_card_per_customer(self):
        self.env['gara.member.card'].create({
            'partner_id': self.partner.id,
            'membership_type_id': self.membership_vip.id,
            'state': 'active',
        })
        with self.assertRaises(ValidationError):
            self.env['gara.member.card'].create({
                'partner_id': self.partner.id,
                'membership_type_id': self.membership_vip.id,
                'state': 'active',
            })

    def test_expiry_date_must_not_be_before_issue_date(self):
        with self.assertRaises(ValidationError):
            self.env['gara.member.card'].create({
                'partner_id': self.partner.id,
                'membership_type_id': self.membership_vip.id,
                'issue_date': '2026-04-23',
                'expiry_date': '2026-04-22',
            })
