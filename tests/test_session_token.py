# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from odoo.addons.troxanh_zmini.utils.session_token import make_token, read_token


@tagged('post_install', '-at_install', 'troxanh_zmini')
class TestTroxanhSessionToken(TransactionCase):

    def test_roundtrip(self):
        t = make_token(123, 'secret_key_for_test________________', ttl_seconds=3600)
        p = read_token(t, 'secret_key_for_test________________')
        self.assertIsNotNone(p)
        self.assertEqual(p['uid'], 123)

    def test_wrong_secret(self):
        t = make_token(1, 'secret_a', ttl_seconds=60)
        self.assertIsNone(read_token(t, 'secret_b'))

    def test_expired(self):
        t = make_token(1, 'secret_key_for_test________________', ttl_seconds=-10)
        self.assertIsNone(read_token(t, 'secret_key_for_test________________'))
