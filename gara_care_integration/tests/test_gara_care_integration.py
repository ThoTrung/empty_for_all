# -*- coding: utf-8 -*-

from psycopg2 import IntegrityError
from unittest.mock import patch

from odoo.tools import mute_logger
from odoo.tests.common import tagged, TransactionCase


@tagged('post_install', '-at_install', 'gara_care_integration')
class TestGaraCareIntegration(TransactionCase):

    def test_template_log_mark_sent_creates_care_activity(self):
        partner = self.env['res.partner'].create({
            'name': 'Care Customer',
            'mobile': '0900000000',
        })
        template = self.env['gara.care.message.template'].create({
            'name': 'Service reminder',
            'channel': 'sms',
            'subject': 'Reminder',
            'body': 'Xin chao {partner}, xe {vehicle}, vu viec {case}.',
        })
        log = self.env['gara.care.communication.log'].create({
            'name': template.subject,
            'partner_id': partner.id,
            'template_id': template.id,
            'channel': template.channel,
            'phone': partner.mobile,
            'message_body': template.body,
        })

        log.action_mark_sent()

        self.assertEqual(log.state, 'sent')
        self.assertIn('Care Customer', log.rendered_body)
        activity = self.env['gara.care.activity'].search([
            ('partner_id', '=', partner.id),
            ('channel', '=', 'sms'),
            ('name', '=', 'Reminder'),
        ], limit=1)
        self.assertTrue(activity)

    def test_provider_code_is_unique(self):
        self.env['gara.care.provider'].create({
            'name': 'Provider 1',
            'code': 'sms-test',
            'channel': 'sms',
        })
        with mute_logger('odoo.sql_db'), self.assertRaises(IntegrityError), self.env.cr.savepoint():
            self.env['gara.care.provider'].create({
                'name': 'Provider 2',
                'code': 'sms-test',
                'channel': 'sms',
            })

    def test_send_now_calls_http_provider_and_marks_sent(self):
        partner = self.env['res.partner'].create({
            'name': 'Provider Customer',
            'mobile': '0911111111',
        })
        provider = self.env['gara.care.provider'].create({
            'name': 'HTTP SMS',
            'code': 'http-sms',
            'channel': 'sms',
            'endpoint_url': 'https://provider.example/send',
            'api_key': 'secret',
            'sender_name': 'ZGARA',
            'payload_template': '{"to": "{phone}", "content": "{message}", "brand": "{sender}"}',
            'success_path': 'ok',
            'external_ref_path': 'data.id',
            'error_path': 'error',
        })
        log = self.env['gara.care.communication.log'].create({
            'name': 'Send test',
            'partner_id': partner.id,
            'provider_id': provider.id,
            'channel': 'sms',
            'phone': partner.mobile,
            'message_body': 'Xin chao {partner}',
        })

        with patch('odoo.addons.gara_care_integration.models.care_integration.requests.post') as mocked_post:
            mocked_post.return_value.json.return_value = {'ok': True, 'data': {'id': 'MSG-1'}}
            mocked_post.return_value.raise_for_status.return_value = None
            log.action_send_now()

        self.assertEqual(log.state, 'sent')
        self.assertEqual(log.external_ref, 'MSG-1')
        self.assertIn('MSG-1', log.response_payload)
        mocked_post.assert_called_once()
        _, kwargs = mocked_post.call_args
        self.assertEqual(kwargs['json']['to'], partner.mobile)
        self.assertIn('Provider Customer', kwargs['json']['content'])

    def test_provider_failure_marks_log_failed(self):
        partner = self.env['res.partner'].create({
            'name': 'Failed Customer',
            'mobile': '0922222222',
        })
        provider = self.env['gara.care.provider'].create({
            'name': 'Fail SMS',
            'code': 'fail-sms',
            'channel': 'sms',
            'endpoint_url': 'https://provider.example/send',
            'success_path': 'ok',
            'error_path': 'error.message',
        })
        log = self.env['gara.care.communication.log'].create({
            'name': 'Fail test',
            'partner_id': partner.id,
            'provider_id': provider.id,
            'channel': 'sms',
            'phone': partner.mobile,
            'message_body': 'Xin chao {partner}',
        })

        with patch('odoo.addons.gara_care_integration.models.care_integration.requests.post') as mocked_post:
            mocked_post.return_value.json.return_value = {'ok': False, 'error': {'message': 'Quota exceeded'}}
            mocked_post.return_value.raise_for_status.return_value = None
            log.action_send_now()

        self.assertEqual(log.state, 'failed')
        self.assertIn('Quota exceeded', log.error_message)
