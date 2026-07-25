# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class RentalLinkChildContactWizard(models.TransientModel):
    _name = "rental.link_child_contact.wizard"
    _description = "Gắn đại diện / liên hệ có sẵn vào công ty"

    parent_partner_id = fields.Many2one(
        "res.partner",
        string="Công ty",
        required=True,
        readonly=True,
    )
    company_scope_id = fields.Many2one(
        "res.company",
        string="Phạm vi công ty (Odoo)",
        compute="_compute_company_scope_id",
    )
    allowed_partner_ids = fields.Many2many(
        "res.partner",
        string="User nội bộ (liên hệ)",
        compute="_compute_allowed_partner_ids",
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Đại diện / liên hệ",
        required=True,
        domain="[('id', 'in', allowed_partner_ids)]",
        help="User nội bộ cùng công ty Odoo; không gồm user thuộc nhóm Rental Administrator.",
    )

    @api.depends("parent_partner_id", "parent_partner_id.company_id")
    def _compute_company_scope_id(self):
        for wiz in self:
            p = wiz.parent_partner_id
            wiz.company_scope_id = (p.company_id or self.env.company) if p else self.env.company

    @api.depends("company_scope_id")
    def _compute_allowed_partner_ids(self):
        Users = self.env["res.users"].sudo()
        Partner = self.env["res.partner"]
        for wiz in self:
            cid = wiz.company_scope_id.id
            if not cid:
                wiz.allowed_partner_ids = Partner
                continue
            users = Users.search(
                [
                    ("active", "=", True),
                    ("share", "=", False),
                    "|",
                    ("company_ids", "in", [cid]),
                    ("company_id", "=", cid),
                ]
            )
            admin_group = self.env.ref("rental.group_rental_admin")
            users = users.filtered(lambda u: admin_group not in u.groups_id)
            partners = users.mapped("partner_id").filtered(lambda p: p and not p.is_company)
            wiz.allowed_partner_ids = partners

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        pid = self.env.context.get("default_parent_partner_id")
        if pid and "parent_partner_id" in fields_list:
            res["parent_partner_id"] = pid
        return res

    def action_link(self):
        self.ensure_one()
        parent = self.parent_partner_id
        if not parent.is_company:
            raise UserError(_("Chỉ áp dụng trên form công ty."))
        contact = self.partner_id
        if contact.is_company:
            raise UserError(_("Hãy chọn một liên hệ cá nhân, không phải công ty."))
        if contact == parent:
            raise UserError(_("Không thể chọn chính công ty."))
        if contact in parent.child_ids:
            raise UserError(_("Liên hệ này đã là đại diện của công ty."))

        if contact not in self.allowed_partner_ids:
            raise UserError(
                _("Chỉ được chọn contact gắn với user nội bộ (internal) của công ty Odoo tương ứng (không gồm Rental Administrator).")
            )

        old_parent = contact.parent_id
        contact.write(
            {
                "parent_id": parent.id,
                "type": "contact",
            }
        )
        if old_parent and old_parent != parent:
            parent.message_post(
                body=_(
                    "Đã gắn đại diện %(name)s (trước đó thuộc: %(old)s).",
                    name=contact.display_name,
                    old=old_parent.display_name,
                ),
            )
        return {"type": "ir.actions.act_window_close"}
