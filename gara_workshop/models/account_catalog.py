# -*- coding: utf-8 -*-

from odoo import fields, models


class GaraAccountCatalog(models.Model):
    """Reference chart of accounts (e.g. TT200 / workshop mapping), not Odoo account.account."""
    _name = 'gara.account.catalog'
    _description = 'Gara accounting account catalog'
    _order = 'code'
    _parent_name = 'parent_id'
    _parent_store = True

    code = fields.Char(string='Mã số', required=True, index=True)
    name = fields.Char(string='Tên tài khoản', required=True)
    parent_id = fields.Many2one(
        'gara.account.catalog',
        string='TK cấp trên',
        ondelete='restrict',
        index=True,
    )
    parent_path = fields.Char(index=True, unaccent=False)
    is_detail = fields.Boolean(string='Chi tiết', default=False)
    nature_code = fields.Char(string='Mã tính chất')
    nature_name = fields.Char(string='Tính chất')
    account_class = fields.Char(string='Loại tài khoản')

    _sql_constraints = [
        ('gara_account_catalog_code_unique', 'unique(code)', 'The account code must be unique.'),
    ]

    def name_get(self):
        return [(rec.id, '%s %s' % (rec.code, rec.name)) for rec in self]
