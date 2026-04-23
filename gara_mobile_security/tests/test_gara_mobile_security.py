# -*- coding: utf-8 -*-

from odoo.exceptions import ValidationError
from odoo.tests.common import tagged, TransactionCase


@tagged('post_install', '-at_install', 'gara_mobile_security')
class TestGaraMobileSecurity(TransactionCase):

    def test_role_feature_matrix(self):
        group = self.env.ref('gara_workshop.group_gara_workshop_user')
        feature = self.env['gara.mobile.role.feature'].create({
            'name': 'Workshop cases',
            'code': 'workshop_case',
            'group_id': group.id,
            'app_scope': 'mobile',
            'can_read': True,
            'can_write': True,
        })

        self.assertEqual(feature.group_id, group)
        self.assertTrue(feature.can_read)
        self.assertTrue(feature.can_write)
        self.assertFalse(feature.can_unlink)

    def test_display_setting_owner_validation(self):
        group = self.env.ref('gara_workshop.group_gara_workshop_user')

        with self.assertRaises(ValidationError):
            self.env['gara.mobile.display.setting'].create({
                'model_name': 'gara.workshop.case',
                'field_name': 'partner_id',
                'user_id': self.env.user.id,
                'group_id': group.id,
            })

        setting = self.env['gara.mobile.display.setting'].create({
            'model_name': 'gara.workshop.case',
            'field_name': 'state',
            'group_id': group.id,
            'visible': True,
        })
        self.assertIn('gara.workshop.case.state', setting.name)

    def test_status_color_config(self):
        color = self.env['gara.mobile.status.color'].create({
            'model_name': 'gara.workshop.case',
            'state_value': 'done',
            'label': 'Done',
            'color': 10,
            'hex_color': '#16a34a',
        })

        self.assertIn('done', color.name)
        self.assertEqual(color.hex_color, '#16a34a')
