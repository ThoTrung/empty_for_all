from odoo import models, fields, api, _
from odoo.exceptions import UserError

class ResPartner(models.Model):
    _inherit = 'res.partner'

    customer_type = fields.Selection(
        [
            ("renter", "Renter"),
            ("driver", "Driver"),
            ("my_company_profile", "My company_profile"),
            ("other", "Other"),
        ],
        string="Customer Type",
        index=True,
        tracking=True,
        help="Classify this contact for rental operations."
    )
    bank_account = fields.Char(string="Bank account")
    id_number = fields.Char(string='ID number', tracking=3)
    birthday = fields.Date(string='Birthday')
    id_issued_by = fields.Char(string='ID issued by')
    id_issued_date = fields.Date(string='Issued Date')
    id_permanent_residence = fields.Char(string="Permanent Residence")
    id_temporary_residence = fields.Char(string="Temporary Residence")
    fax = fields.Char(string="Fax")

    # company_id = fields.Many2one(
    #     'res.company',
    #     required=True,  # <— force ownership
    #     default=lambda self: self.env.company,
    #     index=True,
    #     ondelete='restrict',
    # )
    company_group_id = fields.Many2one(
        'res.company',
        related='company_id.company_group_id',
        store=True, index=True, readonly=True,
    )

    rental_contract_ids = fields.One2many(
        'rental.contract',
        'a_company_party',
        string='Rental contracts'
    )

    @api.depends('name', 'parent_id')
    def _compute_display_name(self):
        """Affect display_name in lists/tree views"""
        if self.env.context.get('no_parent_prefix'):
            for p in self:
                p.display_name = p.name or ''
        else:
            super()._compute_display_name()

    def action_open_link_representative_wizard(self):
        self.ensure_one()
        if not self.is_company:
            raise UserError(_("Chỉ dùng trên liên hệ dạng công ty."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Gắn đại diện có sẵn"),
            "res_model": "rental.link_child_contact.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_parent_partner_id": self.id,
            },
        }

    @api.model_create_multi
    def create(self, vals_list):
        """Only enforce company_id when our context asks for it."""
        customer_type = self.env.context.get('default_customer_type')
        if customer_type:
            """ If exist customer_type - that mean this is create by Customer in module, not Admin in setting page"""
            for vals in vals_list:
                vals['company_id'] = self.env.company.id
        return super().create(vals_list)

    # def action_open_my_company_profile(self):
    #     """Open My Profile directly if only one partner matches the domain."""
    #     domain = [
    #         ('customer_type', '=', False),
    #         ('is_company', '=', True),
    #     ]
    #     partners = self.search(domain)
    #     ctx = {
    #         'my_profile_mode': True,
    #     }
    #     action = {
    #         'type': 'ir.actions.act_window',
    #         'name': _('My Profile'),
    #         'context': ctx,
    #         'res_model': 'res.partner',
    #         'domain': domain,
    #         'view_mode': 'form',
    #     }
    #     if len(partners) == 1:
    #         # ✅ open the single record directly in form view
    #         action.update({
    #             'res_id': partners.id,
    #             'view_mode': 'form',
    #             'views': [(False, 'form')],
    #         })
    #     else:
    #         # ✅ open list view if multiple results (fallback)
    #         action.update({
    #             'view_mode': 'tree,form',
    #             'views': [(False, 'tree'), (False, 'form')],
    #         })
    #
    #     return action
