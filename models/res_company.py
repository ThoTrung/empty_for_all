# company_extra_info/models/res_company.py
from odoo import api, fields, models

class ResCompany(models.Model):
    _inherit = "res.company"

    company_group_id = fields.Many2one(
        "res.company",
        string="Company Group (Root)",
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
