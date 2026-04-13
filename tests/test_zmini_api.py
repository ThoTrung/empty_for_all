# -*- coding: utf-8 -*-
import json
import uuid
from unittest.mock import patch

from odoo.tests import tagged
from odoo.tests.common import HttpCase


@tagged('post_install', '-at_install', 'troxanh_zmini')
class TestTroxanhZminiHttp(HttpCase):

    def setUp(self):
        super().setUp()
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param('troxanh_zmini.jwt_secret', 'http_test_jwt_secret__________________')
        icp.set_param('troxanh_zmini.zalo_app_secret', 'http_test_zalo_app_secret________')

    @patch(
        'odoo.addons.troxanh_zmini.controllers.zmini_api.fetch_zalo_verified_phone_number',
        return_value='84991112233',
    )
    def test_auth_zalo_returns_guest_when_no_user(self, _mock):
        res = self.url_open(
            '/troxanh_zmini/api/v1/auth/zalo',
            data=json.dumps({'access_token': 't', 'code': 'c'}),
            headers=[('Content-Type', 'application/json')],
            timeout=60,
        )
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.content.decode('utf-8'))
        self.assertEqual(data.get('user_type'), 'guest')

    def test_auth_zalo_returns_tenant_jwt(self):
        phone = '8499222' + uuid.uuid4().hex[:6]
        self.env['res.users'].create({
            'name': 'Zmini Tenant',
            'login': phone,
            'password': 'x',
            'custom_user_type': 'portal',
            'customer_type': 'rental_user',
        })
        with patch(
            'odoo.addons.troxanh_zmini.controllers.zmini_api.fetch_zalo_verified_phone_number',
            return_value=phone,
        ):
            res = self.url_open(
                '/troxanh_zmini/api/v1/auth/zalo',
                data=json.dumps({'access_token': 't', 'code': 'c'}),
                headers=[('Content-Type', 'application/json')],
                timeout=60,
            )
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.content.decode('utf-8'))
        self.assertEqual(data.get('user_type'), 'tenant')
        self.assertTrue(data.get('access_token'))

        me = self.url_open(
            '/troxanh_zmini/api/v1/me',
            headers=[('Authorization', 'Bearer %s' % data['access_token'])],
            timeout=60,
        )
        self.assertEqual(me.status_code, 200)
        me_data = json.loads(me.content.decode('utf-8'))
        self.assertEqual(me_data.get('name'), 'Zmini Tenant')
