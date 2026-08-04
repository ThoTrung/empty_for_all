from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.osv import expression

class ResPartner(models.Model):
    _inherit = 'res.partner'

    customer_type = fields.Selection(
        [
            ("company", "Công ty"),
            ("driver", "Tài xế"),
            ("my_company_profile", "Hồ sơ công ty"),
            ("other", "Khác"),
        ],
        string="Kiểu form",
        index=True,
        tracking=True,
        help="Chế độ form (layout): công ty / tài xế / hồ sơ công ty / khác. "
             "Vai trò nghiệp vụ dùng checkbox Khách thuê / NCC (DEC-29).",
    )
    is_rental_customer = fields.Boolean(
        string="Khách thuê",
        default=False,
        index=True,
        tracking=True,
        help="Đối tác thuê hàng của công ty (có thể đồng thời là NCC).",
    )
    is_rental_supplier = fields.Boolean(
        string="NCC",
        default=False,
        index=True,
        tracking=True,
        help="Nhà cung cấp thuê ngoài; có thể đồng thời là Khách thuê (giá NCC↔NCC).",
    )
    bank_account = fields.Char(string="Tài khoản ngân hàng")
    id_number = fields.Char(string='Số CCCD/CMND', tracking=3)
    birthday = fields.Date(string='Ngày sinh')
    id_issued_by = fields.Char(string='Nơi cấp')
    id_issued_date = fields.Date(string='Ngày cấp')
    id_permanent_residence = fields.Char(string="Thường trú")
    id_temporary_residence = fields.Char(string="Tạm trú")
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
        string='Hợp đồng thuê'
    )

    @api.depends('name', 'parent_id')
    def _compute_display_name(self):
        """Affect display_name in lists/tree views"""
        if self.env.context.get('no_parent_prefix'):
            for p in self:
                p.display_name = p.name or ''
        else:
            super()._compute_display_name()

    @api.model
    def _get_view(self, view_id=None, view_type='form', **options):
        """Drop IAP partner_autocomplete widget; keep plain text/char inputs."""
        arch, view = super()._get_view(view_id, view_type, **options)
        if view_type == 'form':
            for node in arch.xpath("//field[@name='name']|//field[@name='vat']"):
                if node.attrib.get('widget') != 'field_partner_autocomplete':
                    continue
                if node.get('name') == 'name':
                    node.attrib['widget'] = 'text'
                else:
                    node.attrib.pop('widget', None)
        return arch, view

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        """Honor domain pushed from DomainSelector patch via context."""
        args = list(args or [])
        extra = self.env.context.get('rental_partner_name_search_domain')
        if extra:
            args = expression.AND([args, list(extra)])
        return super().name_search(name, args=args, operator=operator, limit=limit)

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

    @api.model
    def _rental_align_role_vals(self, vals, record=None):
        """Force company form mode when a rental role is (or stays) enabled."""
        will_customer = (
            vals['is_rental_customer']
            if 'is_rental_customer' in vals
            else (record.is_rental_customer if record else False)
        )
        will_supplier = (
            vals['is_rental_supplier']
            if 'is_rental_supplier' in vals
            else (record.is_rental_supplier if record else False)
        )
        if not (will_customer or will_supplier):
            return vals
        vals = dict(vals)
        vals['is_company'] = True
        vals['customer_type'] = 'company'
        return vals

    def _rental_has_active_customer_contracts(self):
        self.ensure_one()
        return bool(self.env['rental.contract'].search([
            ('a_company_party', '=', self.id),
            ('status', '=', 'active'),
        ], limit=1))

    def _rental_has_active_supplier_contracts(self):
        self.ensure_one()
        if 'rental.subrent.contract' not in self.env:
            return False
        return bool(self.env['rental.subrent.contract'].search([
            ('supplier_id', '=', self.id),
            ('state', '=', 'active'),
        ], limit=1))

    def _rental_warn_clearing_roles(self, vals):
        """Soft warn (chatter) when clearing a role while active contracts remain."""
        if self.env.context.get('rental_skip_role_clear_warn'):
            return
        clear_customer = (
            'is_rental_customer' in vals and not vals.get('is_rental_customer')
        )
        clear_supplier = (
            'is_rental_supplier' in vals and not vals.get('is_rental_supplier')
        )
        if not (clear_customer or clear_supplier):
            return
        for partner in self:
            notes = []
            if (
                clear_customer
                and partner.is_rental_customer
                and partner._rental_has_active_customer_contracts()
            ):
                notes.append(_(
                    "Đã tắt «Khách thuê» trong khi còn hợp đồng thuê đang hiệu lực."
                ))
            if (
                clear_supplier
                and partner.is_rental_supplier
                and partner._rental_has_active_supplier_contracts()
            ):
                notes.append(_(
                    "Đã tắt «NCC» trong khi còn hợp đồng thuê ngoài đang hiệu lực."
                ))
            if notes and hasattr(partner, 'message_post'):
                partner.message_post(body="<br/>".join(notes))

    @api.constrains(
        'is_rental_customer', 'is_rental_supplier', 'is_company', 'customer_type',
    )
    def _check_rental_roles_company_form(self):
        for partner in self:
            if not (partner.is_rental_customer or partner.is_rental_supplier):
                continue
            if not partner.is_company or partner.customer_type != 'company':
                raise ValidationError(_(
                    "Vai trò Khách thuê / NCC chỉ dùng cho liên hệ công ty "
                    "(kiểu form = Công ty). Partner: %s"
                ) % (partner.display_name or partner.name or partner.id))

    @api.onchange('is_rental_customer', 'is_rental_supplier')
    def _onchange_rental_roles(self):
        if self.is_rental_customer or self.is_rental_supplier:
            self.is_company = True
            self.customer_type = 'company'
        origin = self._origin
        if not (origin and origin.id):
            return
        warning = self._rental_build_role_clear_warning(
            origin,
            clearing_customer=origin.is_rental_customer and not self.is_rental_customer,
            clearing_supplier=origin.is_rental_supplier and not self.is_rental_supplier,
        )
        if warning:
            return {'warning': warning}

    @api.model
    def _rental_build_role_clear_warning(
        self, origin, *, clearing_customer=False, clearing_supplier=False,
    ):
        """Return onchange warning dict when clearing a role with active HĐ."""
        if not origin:
            return None
        if clearing_customer and origin._rental_has_active_customer_contracts():
            return {
                'title': _('Cảnh báo'),
                'message': _(
                    "Partner còn hợp đồng thuê đang hiệu lực. "
                    "Tắt «Khách thuê» sẽ ẩn khỏi danh sách chọn HĐ mới."
                ),
            }
        if clearing_supplier and origin._rental_has_active_supplier_contracts():
            return {
                'title': _('Cảnh báo'),
                'message': _(
                    "Partner còn hợp đồng thuê ngoài đang hiệu lực. "
                    "Tắt «NCC» sẽ ẩn khỏi danh sách chọn HĐ mới."
                ),
            }
        return None

    @api.model_create_multi
    def create(self, vals_list):
        """Always stamp company_id so commercial partners are not shared globally.

        Skip when creating the partner for a new ``res.company`` (warehouse setup
        requires company_id False/unset until the company row exists).
        """
        if self.env.context.get('skip_company_id_stamp'):
            aligned = [self._rental_align_role_vals(dict(v)) for v in vals_list]
            return super().create(aligned)
        prepared = []
        for vals in vals_list:
            vals = self._rental_align_role_vals(dict(vals))
            if not vals.get('company_id'):
                parent_id = vals.get('parent_id')
                if parent_id:
                    parent = self.browse(parent_id)
                    if parent.company_id:
                        vals['company_id'] = parent.company_id.id
                    else:
                        vals['company_id'] = self.env.company.id
                else:
                    vals['company_id'] = self.env.company.id
            prepared.append(vals)
        return super().create(prepared)

    def write(self, vals):
        vals = dict(vals)
        self._rental_warn_clearing_roles(vals)
        if len(self) <= 1:
            vals = self._rental_align_role_vals(vals, self[:1] if self else None)
            return super().write(vals)
        role_in_vals = (
            'is_rental_customer' in vals or 'is_rental_supplier' in vals
        )
        form_clash = (
            ('customer_type' in vals or 'is_company' in vals)
            and any(p.is_rental_customer or p.is_rental_supplier for p in self)
        )
        if not role_in_vals and not form_clash:
            return super().write(vals)
        # Per-record align: roles may stay on while form fields change in batch.
        for partner in self:
            partner_vals = self._rental_align_role_vals(dict(vals), partner)
            super(ResPartner, partner).write(partner_vals)
        return True
