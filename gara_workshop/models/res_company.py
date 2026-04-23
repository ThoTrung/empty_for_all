# -*- coding: utf-8 -*-

from odoo import api, fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    gara_close_approval_threshold = fields.Monetary(
        string='Gara close approval threshold',
        currency_field='currency_id',
        default=0.0,
        help='If case SO total exceeds this amount, closing requires approved request.',
    )
    gara_insurance_approval_threshold = fields.Monetary(
        string='Gara insurance approval threshold',
        currency_field='currency_id',
        default=0.0,
        help='If insurance approved amount exceeds this amount, manager approval is required.',
    )
    gara_quote_require_approval = fields.Boolean(
        string='Require approval before quotation confirmation',
        default=False,
    )
    gara_member_point_rate = fields.Float(
        string='Member point rate',
        default=0.0,
        help='Points earned per 1 currency unit on service payment. Example 0.001 = 1 point / 1,000 currency.',
    )

    def _gara_account_by_code(self, code):
        self.ensure_one()
        return self.env['account.account'].with_company(self).search(
            [('company_id', '=', self.id), ('code', '=', code)],
            limit=1,
        )

    def gara_apply_vn_product_account_defaults(self):
        """Map default Gara products to common TT200 accounts (via l10n_vn CoA).

        - Service labour → 5113 (service revenue), optional expense ref 622.
        - Repair consumable unit → 5111 (goods revenue), 632 (COGS).
        - Sets company default sale VAT on products if they have no customer tax.
        """
        labour = self.env.ref('gara_workshop.product_gara_labour', raise_if_not_found=False)
        repair = self.env.ref('gara_workshop.product_gara_repair_subject', raise_if_not_found=False)
        if not labour or not repair:
            return
        for company in self:
            if company.account_fiscal_country_id.code != 'VN':
                continue
            acc_5113 = company._gara_account_by_code('5113')
            acc_5111 = company._gara_account_by_code('5111')
            acc_632 = company._gara_account_by_code('632')
            acc_622 = company._gara_account_by_code('622')
            if not (acc_5113 or acc_5111):
                continue
            sale_tax = company.account_sale_tax_id
            for product in labour | repair:
                tmpl = product.product_tmpl_id
                tmpl_c = tmpl.with_company(company)
                vals = {}
                if product == labour and acc_5113:
                    vals['property_account_income_id'] = acc_5113.id
                    if acc_622:
                        vals['property_account_expense_id'] = acc_622.id
                elif product == repair and acc_5111:
                    vals['property_account_income_id'] = acc_5111.id
                    if acc_632:
                        vals['property_account_expense_id'] = acc_632.id
                if vals:
                    tmpl_c.write(vals)
                if sale_tax and not tmpl_c.taxes_id:
                    tmpl_c.write({'taxes_id': [(6, 0, sale_tax.ids)]})

    @api.model
    def gara_apply_vn_product_defaults_all_companies(self):
        """Called from post-install hook."""
        for company in self.env['res.company'].search([]):
            company.gara_apply_vn_product_account_defaults()
