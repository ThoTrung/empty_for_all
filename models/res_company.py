# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    company_group_id = fields.Many2one(
        "res.company",
        string="Nhóm công ty (gốc)",
        compute="_compute_company_group_id",
        store=True,
        index=True,
    )

    @api.depends('parent_id', 'parent_id.parent_id')  # minimal; full safety below
    def _compute_company_group_id(self):
        for c in self:
            root = c
            while root.parent_id:
                root = root.parent_id
            c.company_group_id = root.id

    @api.model_create_multi
    def create(self, vals_list):
        # Partner created inside base create must not get env.company stamped
        # (breaks stock warehouse _check_company on the new company).
        companies = super(
            ResCompany, self.with_context(skip_company_id_stamp=True)
        ).create(vals_list)
        for company in companies:
            partner = company.partner_id
            if partner and partner.company_id != company:
                partner.sudo().write({"company_id": company.id})
        return companies
