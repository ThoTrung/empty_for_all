# models/mc_mixin.py
from odoo import fields, models


class MultiCompanyGroupMixin(models.AbstractModel):
    _name = 'mc.group.mixin'
    _description = 'Mixin nhóm đa công ty'
    _check_company_auto = True

    company_id = fields.Many2one(
        'res.company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
        ondelete='restrict',
    )
    # Mirrors the top/root company of the record’s company
    company_group_id = fields.Many2one(
        'res.company',
        related='company_id.company_group_id',
        store=True,
        index=True,
        readonly=True,
    )
