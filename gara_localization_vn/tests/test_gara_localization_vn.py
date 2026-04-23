# -*- coding: utf-8 -*-

from odoo.exceptions import ValidationError
from odoo.tests.common import tagged, TransactionCase


@tagged('post_install', '-at_install', 'gara_localization_vn')
class TestGaraLocalizationVn(TransactionCase):

    def test_seed_address_catalogs(self):
        province = self.env.ref('gara_localization_vn.vn_province_hanoi')
        district = self.env.ref('gara_localization_vn.vn_district_ba_dinh')
        ward = self.env.ref('gara_localization_vn.vn_ward_phuc_xa')

        self.assertEqual(province.country_id, self.env.ref('base.vn'))
        self.assertEqual(district.province_id, province)
        self.assertEqual(ward.district_id, district)
        self.assertEqual(ward.province_id, province)

    def test_partner_vn_address_hierarchy(self):
        province = self.env.ref('gara_localization_vn.vn_province_hanoi')
        district = self.env.ref('gara_localization_vn.vn_district_ba_dinh')
        ward = self.env.ref('gara_localization_vn.vn_ward_phuc_xa')

        partner = self.env['res.partner'].create({
            'name': 'Vietnam Address Customer',
            'gara_vn_province_id': province.id,
            'gara_vn_district_id': district.id,
            'gara_vn_ward_id': ward.id,
        })

        self.assertEqual(partner.gara_vn_province_id, province)
        self.assertEqual(partner.gara_vn_district_id, district)
        self.assertEqual(partner.gara_vn_ward_id, ward)

    def test_partner_rejects_wrong_address_hierarchy(self):
        hanoi = self.env.ref('gara_localization_vn.vn_province_hanoi')
        hcm_district = self.env.ref('gara_localization_vn.vn_district_1')

        with self.assertRaises(ValidationError):
            self.env['res.partner'].create({
                'name': 'Invalid Vietnam Address Customer',
                'gara_vn_province_id': hanoi.id,
                'gara_vn_district_id': hcm_district.id,
            })
