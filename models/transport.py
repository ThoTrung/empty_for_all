# models/transport.py
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging
from datetime import date

_logger = logging.getLogger(__name__)


class Transport(models.Model):
    _name = "rr.transport"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Transport"
    _order = "start_rental_or_return_date"
    _rec_name = 'code'

    name = fields.Char(string="Name")
    code = fields.Char(string="Code", copy=False, index=True)
    rental_contract_id = fields.Many2one(
        'rental.contract',
        string="Rental contract",
        ondelete='cascade',
        index=True,
        tracking=2,
        groups='rental.group_rental_staff',
    )
    rental_contract_summary = fields.Char(
        string='Hợp đồng (hiển thị)',
        compute='_compute_rental_contract_summary',
    )
    type = fields.Selection([
        ('delivery', 'Delivery'),
        ('return', 'Return'),
        ('compensation', 'Đền bù'),
    ], string="Type", default='delivery', required=True, tracking=3)
    driver_id = fields.Many2one(
        'res.partner',
        string="Driver",
        domain="[('customer_type', '=', 'driver')]",
        required=True,
        tracking=4,
    )
    start_rental_or_return_date = fields.Date(string='Start rental or return date', required=True, tracking=5)
    delivering_party = fields.Many2one('res.partner', string='Delivering party', compute='_compute_delivering_receiving_party', store=True, tracking=6)
    delivering_party_parent_id = fields.Many2one(
        'res.partner',
        string='Delivering party company',
        related='delivering_party.parent_id',
        readonly=True,
    )
    deliverer_partner_id = fields.Many2one(
        'res.partner',
        string='Người giao',
        help='Người thực hiện giao hàng (mặc định theo đại diện hợp đồng bên giao).',
        required=True,
        tracking=True,
    )
    dp_name = fields.Char(string='Delivering party', compute='_compute_delivering_receiving_party', store=True)
    dp_owner_name = fields.Char(string='DP owner name', compute='_compute_delivering_receiving_party', store=True)
    dp_owner_function = fields.Char(string='DP owner function', compute='_compute_delivering_receiving_party', store=True)
    dp_party_phone = fields.Char(
        string='SĐT đại diện (bên giao)',
        compute='_compute_delivering_receiving_party',
        store=True,
    )
    deliverer_phone = fields.Char(string='SĐT người giao', compute='_compute_delivering_receiving_party', store=True)
    deliverer_id_number = fields.Char(string='CCCD người giao', compute='_compute_delivering_receiving_party', store=True)
    deliverer_partner_function = fields.Char(
        string='Chức vụ người giao',
        compute='_compute_delivering_receiving_party',
        store=True,
    )

    receiving_party = fields.Many2one('res.partner', string='Receiving party', compute='_compute_delivering_receiving_party', store=True, tracking=7)
    receiving_party_parent_id = fields.Many2one(
        'res.partner',
        string='Receiving party company',
        related='receiving_party.parent_id',
        readonly=True,
    )
    receiver_partner_id = fields.Many2one(
        'res.partner',
        string='Người nhận',
        help='Người thực hiện nhận hàng (mặc định theo đại diện hợp đồng bên nhận).',
        required=True,
        tracking=True,
    )
    rp_name = fields.Char(string='Receiving party', compute='_compute_delivering_receiving_party', store=True)
    rp_owner_name = fields.Char(string='RP owner name', compute='_compute_delivering_receiving_party', store=True)
    rp_owner_function = fields.Char(string='RP owner function', compute='_compute_delivering_receiving_party', store=True)
    rp_party_phone = fields.Char(
        string='SĐT đại diện (bên nhận)',
        compute='_compute_delivering_receiving_party',
        store=True,
    )
    receiver_phone = fields.Char(string='SĐT người nhận', compute='_compute_delivering_receiving_party', store=True)
    receiver_id_number = fields.Char(string='CCCD người nhận', compute='_compute_delivering_receiving_party', store=True)
    receiver_partner_function = fields.Char(
        string='Chức vụ người nhận',
        compute='_compute_delivering_receiving_party',
        store=True,
    )

    driver_name = fields.Char(string="Driver", compute='_compute_driver', store=True, tracking=8)
    driver_phone = fields.Char(string="Driver Phone", compute='_compute_driver', store=True)
    transport_truck_id = fields.Many2one('transport.truck', name='Transport truck', required=True, tracking=9)
    plate = fields.Char(string="Plate", compute='_compute_plate', store=True)
    vehicle_start_time = fields.Datetime(string="Vehicle start time", required=True, default=date.today(), tracking=10)
    vehicle_arrival_time = fields.Datetime(string="Vehicle arrival time", tracking=11)
    fee = fields.Float(string="Transport Fee", default=0, tracking=12)
    # currency_id = fields.Many2one('res.currency', string='Currency', related='sale_order_id.currency_id', store=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Done'),
        ('cancel', 'Cancelled'),
    ], string='Status', default='draft', tracking=13)
    transport_line_ids = fields.One2many('rr.transport.line', 'transport_id', string="Products on truck")
    picking_ids = fields.One2many(
        'stock.picking',
        'rental_transport_id',
        string='Phiếu kho',
        copy=False,
    )
    picking_count = fields.Integer(string='Số phiếu kho', compute='_compute_picking_count')

    construction_work_id = fields.Many2one('construction.work', string="Gói thầu",
                                           compute='_compute_delivering_receiving_party', store=True, tracking=15)
    construction_work_project_id = fields.Many2one(
        'construction.project',
        string="Dự án",
        related='construction_work_id.project_id',
        store=True,
        readonly=True,
    )
    construction_work_address = fields.Char(
        string='Địa chỉ',
        compute='_compute_delivering_receiving_party',
        store=True,
    )

    equipment_carrier = fields.Selection([
        ('a_party_carrier', 'A party carrier'),
        ('b_party_carrier', 'B party carrier'),
    ], string='Equipment carrier', default='a_party_carrier', required=True, tracking=16)
    equipment_carrier_name = fields.Char(string='Equipment carrier name', compute='_compute_equipment_carrier_name')
    equipment_load = fields.Float(string='Equipment load')

    company_id = fields.Many2one(related='rental_contract_id.company_id', store=True, readonly=True, index=True)
    company_group_id = fields.Many2one(related='rental_contract_id.company_group_id', store=True, index=True, readonly=True)
    contract_can_edit = fields.Boolean(
        related="rental_contract_id.can_edit",
        string="Có thể sửa (hợp đồng)",
        readonly=True,
    )
    contract_edit_unlocked = fields.Boolean(
        related="rental_contract_id.edit_unlocked",
        string="Mở khóa sửa (hợp đồng)",
        readonly=True,
    )
    picking_type_id = fields.Many2one(
        'stock.picking.type',
        string='Operation Type',
        required=True,
        default=lambda self: self._default_picking_type_for_type(self.env.context.get('default_type', 'delivery')),
        domain="[('code', '=', type == 'delivery' and 'outgoing' or 'incoming'),"
               " ('warehouse_id.company_id', '=', company_id)]",
    )

    @api.depends('picking_ids')
    def _compute_picking_count(self):
        for rec in self:
            rec.picking_count = len(rec.picking_ids)

    location_id = fields.Many2one('stock.location', string='Source Location')
    location_dest_id = fields.Many2one('stock.location', string='Destination Location')

    # who_pay_transport_fee =

    @api.depends('rental_contract_id', 'rental_contract_id.code', 'rental_contract_id.name')
    def _compute_rental_contract_summary(self):
        """Hiển thị hợp đồng cho user không mở được Many2one (vd. nhóm Người giao/nhận)."""
        for rec in self:
            c = rec.sudo().rental_contract_id
            rec.rental_contract_summary = c.display_name if c else ''

    @api.depends('equipment_carrier', 'rental_contract_id')
    def _compute_equipment_carrier_name(self):
        for rec in self:
            equipment_carrier_name = ''
            if rec.equipment_carrier == 'a_party_carrier':
                equipment_carrier_name = rec.rental_contract_id.a_party.parent_id.name
            elif rec.equipment_carrier == 'b_party_carrier':
                equipment_carrier_name = rec.rental_contract_id.b_party.parent_id.name
            rec.equipment_carrier_name = equipment_carrier_name

    def _delivering_receiving_party_pair(self):
        """Return (delivering_party, receiving_party) from contract and transport type."""
        self.ensure_one()
        contract = self.rental_contract_id
        if not contract:
            return self.env['res.partner'], self.env['res.partner']
        if self.type in ('return', 'compensation'):
            return contract.a_party, contract.b_party
        return contract.b_party, contract.a_party

    @api.model_create_multi
    def create(self, vals_list):
        seq_key = 'rr.transport'
        Seq = self.env['ir.sequence']
        for vals in vals_list:
            raw = vals.get('code')
            if isinstance(raw, str):
                raw = raw.strip()
            else:
                raw = raw or False
            if not raw:
                vals['code'] = Seq.next_by_code(seq_key)
            else:
                vals['code'] = raw
            if not vals.get('code'):
                raise UserError(
                    _("Không tạo được mã phiếu. Kiểm tra chuỗi số (sequence) %(seq)s trong Cài đặt kỹ thuật."),
                    seq=seq_key,
                )
            vals['name'] = vals['code']
            rc_id = vals.get('rental_contract_id')
            if not rc_id:
                continue
            contract = self.env['rental.contract'].browse(rc_id)
            typ = vals.get('type', 'delivery')
            deliv, recv = (contract.a_party, contract.b_party) if typ in ('return', 'compensation') else (contract.b_party, contract.a_party)
            if 'deliverer_partner_id' not in vals and deliv:
                vals['deliverer_partner_id'] = deliv.id
            if 'receiver_partner_id' not in vals and recv:
                vals['receiver_partner_id'] = recv.id
        return super().create(vals_list)

    def write(self, vals):
        vals = dict(vals)
        if vals.get('code'):
            vals['name'] = vals['code']
        res = super().write(vals)
        if vals.get('type') and not self.env.context.get('rr_transport_skip_party_realign'):
            for rec in self:
                d, r = rec._delivering_receiving_party_pair()
                if d and r:
                    rec.with_context(rr_transport_skip_party_realign=True).write({
                        'deliverer_partner_id': d.id,
                        'receiver_partner_id': r.id,
                    })
        return res

    @api.depends(
        'rental_contract_id',
        'rental_contract_id.construction_work_id',
        'rental_contract_id.construction_work_address',
        'type',
        'rental_contract_id.a_party',
        'rental_contract_id.a_party.phone',
        'rental_contract_id.a_party.name',
        'rental_contract_id.a_party.function',
        'rental_contract_id.b_party',
        'rental_contract_id.b_party.phone',
        'rental_contract_id.b_party.name',
        'rental_contract_id.b_party.function',
        'deliverer_partner_id',
        'deliverer_partner_id.phone',
        'deliverer_partner_id.function',
        'deliverer_partner_id.id_number',
        'receiver_partner_id',
        'receiver_partner_id.phone',
        'receiver_partner_id.function',
        'receiver_partner_id.id_number',
    )
    def _compute_delivering_receiving_party(self):
        for rec in self:
            contract = rec.rental_contract_id
            delivering_party, receiving_party = rec._delivering_receiving_party_pair()
            construction_work_id = contract.construction_work_id if contract else False
            construction_work_address = contract.construction_work_address if contract else ''

            rec.delivering_party = delivering_party
            rec.receiving_party = receiving_party
            rec.dp_name = delivering_party.parent_id.name if delivering_party and delivering_party.parent_id else ''
            rec.rp_name = receiving_party.parent_id.name if receiving_party and receiving_party.parent_id else ''

            # Đại diện hợp đồng (theo bên giao / bên nhận) — tách khỏi người giao/nhận
            rec.dp_owner_name = delivering_party.name if delivering_party else ''
            rec.dp_owner_function = delivering_party.function if delivering_party else ''
            rec.dp_party_phone = delivering_party.phone if delivering_party else ''

            rec.rp_owner_name = receiving_party.name if receiving_party else ''
            rec.rp_owner_function = receiving_party.function if receiving_party else ''
            rec.rp_party_phone = receiving_party.phone if receiving_party else ''

            deliv = rec.deliverer_partner_id
            recv = rec.receiver_partner_id
            rec.deliverer_phone = deliv.phone if deliv else ''
            rec.deliverer_id_number = deliv.id_number if deliv else ''
            rec.deliverer_partner_function = deliv.function if deliv else ''

            rec.receiver_phone = recv.phone if recv else ''
            rec.receiver_id_number = recv.id_number if recv else ''
            rec.receiver_partner_function = recv.function if recv else ''

            rec.construction_work_id = construction_work_id
            rec.construction_work_address = construction_work_address

    @api.depends('transport_truck_id')
    def _compute_plate(self):
        for rec in self:
            if rec.transport_truck_id:
                rec.plate = rec.transport_truck_id.plate

    @api.depends('driver_id')
    def _compute_driver(self):
        for rec in self:
            if rec.driver_id:
                rec.driver_name = rec.driver_id.name
                rec.driver_phone = rec.driver_id.phone

    def action_export_equipment_delivery_receipt(self):
        self.ensure_one()
        url = f'/rental/transport/equipment-delivery-receipt/{self.id}/download'
        return {
            'type': 'ir.actions.act_url',
            'url': url,
            'target': 'self',  # or 'new' to open in new tab
        }

    def action_view_pickings(self):
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id('stock.action_picking_tree_all')
        action = dict(action)
        action['domain'] = [('rental_transport_id', '=', self.id)]
        action['context'] = {
            **(self.env.context or {}),
            'default_rental_transport_id': self.id,
            'default_company_id': self.company_id.id,
            'default_picking_type_id': self.picking_type_id.id,
        }
        return action

    def _default_picking_type_for_type(self, t, company=None):
        """Return a sensible picking type for given type ('delivery'/'return')."""
        code = 'outgoing' if t == 'delivery' else 'incoming'
        company = company or self.company_id or self.env.company
        wh_env = self.env['stock.warehouse'].sudo().with_company(company)
        wh = wh_env.search([('company_id', '=', company.id)], limit=1)
        if wh:
            if code == 'outgoing' and wh.out_type_id:
                return wh.out_type_id.id
            if code == 'incoming' and wh.in_type_id:
                return wh.in_type_id.id
        pt_env = self.env['stock.picking.type'].sudo().with_company(company)
        pt = pt_env.search([
            ('code', '=', code),
            ('warehouse_id.company_id', '=', company.id),
        ], limit=1)
        return pt.id if pt else False

    def _apply_picking_type_locations(self):
        """
        Set locations with the following rule:
        - Delivery:   src = internal (or PT default), dest = partner's customer (or Customers; PT default ignored if empty)
        - Return:     src = partner's customer (or Customers), dest = internal (or PT default)
        Priority:
          1) Operation Type defaults if they exist and make sense
          2) Our enforced partner/internal defaults per type
        """
        for rec in self:
            if not rec.picking_type_id:
                rec.location_id = False
                rec.location_dest_id = False
                continue
            pt_src = rec.picking_type_id.default_location_src_id
            pt_dst = rec.picking_type_id.default_location_dest_id
            partner_customer = rec._get_partner_customer_location()
            # internal_stock = rec._get_internal_stock_location()

            if rec.type == 'delivery':
                # Source prefers PT src, else internal; Destination forced to Customer (partner/generic)
                src = pt_src # or internal_stock
                dest = partner_customer or pt_dst  # prefer partner/generic customer; fallback PT dest if somehow custom
            else:  # 'return'
                # Source forced to Customer (partner/generic); Destination prefers PT dest, else internal
                src = partner_customer or pt_src
                dest = pt_dst# or internal_stock

            rec.location_id = src.id if src else False
            rec.location_dest_id = dest.id if dest else False

    @api.onchange('type', 'company_id')
    def _onchange_type_set_picking_type(self):
        """When Type changes, choose a matching picking type and update locations."""
        for rec in self:
            wanted_code = 'outgoing' if rec.type == 'delivery' else 'incoming'
            # If current picking_type doesn’t match the desired code, replace it
            if not rec.picking_type_id or rec.picking_type_id.code != wanted_code:
                pt_id = rec._default_picking_type_for_type(rec.type, company=rec.company_id)
                rec.picking_type_id = pt_id
            # Always refresh locations from the (new) picking type
            rec._apply_picking_type_locations()

    @api.onchange('picking_type_id')
    def _onchange_picking_type_locations(self):
        """If user manually picks a different operation type, refresh locations."""
        self._apply_picking_type_locations()

    def _get_partner_customer_location(self):
        """Partner-specific Customer location; else generic Customers."""
        customer_loc = False
        if self.rental_contract_id.a_party and self.rental_contract_id.a_party.property_stock_customer:
            customer_loc = self.rental_contract_id.a_party.property_stock_customer
        if not customer_loc:
            # generic Customers location
            try:
                customer_loc = self.env.ref('stock.stock_location_customers')
            except Exception:
                customer_loc = False
        return customer_loc

    def action_create_pickings(self):
        self.ensure_one()
        # Đền bù: dòng hỏng 100% (mất/hỏng hoàn toàn) không quay về kho. Nếu toàn bộ
        # dòng đều 100% thì không tạo phiếu nhập kho nào, chỉ đóng phiếu đền bù.
        if self.type == 'compensation' and not self._compensation_lines_to_stock():
            if self.state == 'draft':
                self.write({'state': 'done'})
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("Đền bù"),
                    'message': _("Tất cả sản phẩm hỏng/mất 100% nên không tạo phiếu nhập kho."),
                    'type': 'success',
                    'sticky': False,
                },
            }
        picking = self._rental_create_picking()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'view_mode': 'form',
            'res_id': picking.id,
            'target': 'current',
        }

    def _compensation_lines_to_stock(self):
        """Các dòng đền bù còn nhập lại kho (tỉ lệ hỏng < 100%)."""
        self.ensure_one()
        return self.transport_line_ids.filtered(lambda l: l._compensation_returns_to_stock())

    def _rental_use_stock_sudo(self):
        return bool(self.env.context.get("rental_transport_import"))

    def _rental_stock_model(self, model_name):
        model = self.env[model_name]
        if self._rental_use_stock_sudo():
            company = self.company_id or self.rental_contract_id.company_id
            model = model.sudo()
            if company:
                model = model.with_company(company)
        return model

    def _rental_create_picking(self):
        """Create a stock picking for this draft transport. Returns the picking record."""
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_("Chỉ tạo phiếu kho khi phiếu xuất nhập kho đang ở trạng thái Nháp."))
        if not self.rental_contract_id:
            raise UserError(_("Dont have contract for this transport."))
        if not self.transport_line_ids:
            raise UserError(_("Add at least one line before creating a picking."))

        scheduled_date = self.start_rental_or_return_date or fields.Datetime.now()
        company = self.company_id or self.rental_contract_id.company_id
        work_self = self.with_company(company) if company else self
        pt_id = work_self._default_picking_type_for_type(work_self.type, company=company)
        if pt_id:
            work_self.picking_type_id = pt_id
        work_self._apply_picking_type_locations()
        picking_vals = {
            'picking_type_id': work_self.picking_type_id.id,
            'location_id': work_self.location_id.id,
            'location_dest_id': work_self.location_dest_id.id,
            'company_id': company.id if company else self.company_id.id,
            'rental_transport_id': self.id,
            'origin': self.code or self.name or (self.rental_contract_id and self.rental_contract_id.name) or 'Transport',
            'scheduled_date': scheduled_date,
            'partner_id': self.rental_contract_id.a_party.id,
        }
        picking = self._rental_stock_model("stock.picking").create(picking_vals)

        # Đền bù: chỉ nhập lại kho phần hỏng < 100%; phần hỏng/mất 100% không tạo move.
        lines = self.transport_line_ids
        if self.type == 'compensation':
            lines = self._compensation_lines_to_stock()
            if not lines:
                raise UserError(
                    _("Tất cả sản phẩm hỏng/mất 100% nên không có gì để nhập kho.")
                )

        Move = self._rental_stock_model("stock.move")
        for line in lines:
            if not line.product_id or line.qty <= 0:
                continue
            Move.create({
                'name': line.name or line.product_id.display_name,
                'company_id': company.id if company else self.company_id.id,
                'product_id': line.product_id.id,
                'product_uom_qty': line.qty,
                'product_uom': line.product_id.uom_id.id,
                'picking_id': picking.id,
                'location_id': self.location_id.id,
                'location_dest_id': self.location_dest_id.id,
                'description_picking': line.name or False,
            })

        picking.action_confirm()
        try:
            picking.action_assign()
        except Exception:
            pass
        return picking

    def _rental_validate_picking(self, picking):
        """Validate picking at full qty; allow negative on-hand (historical Excel import)."""
        self.ensure_one()
        picking.ensure_one()
        if self._rental_use_stock_sudo():
            company = self.company_id or self.rental_contract_id.company_id
            picking = picking.sudo()
            if company:
                picking = picking.with_company(company)
        if picking.state == 'done':
            return picking
        if picking.state == 'cancel':
            raise UserError(_("Phiếu kho %(name)s đã bị hủy.") % {"name": picking.display_name})

        if picking.state == 'draft':
            picking.action_confirm()

        # Drop partial reservations so validation can proceed without stock on hand.
        picking.do_unreserve()

        moves = picking.move_ids.filtered(lambda m: m.state not in ('done', 'cancel'))
        for move in moves:
            if not move.product_uom_qty:
                continue
            # quantity inverse creates move lines; picked=True is required in Odoo 17 _action_done.
            move.quantity = move.product_uom_qty
            move.picked = True

        validate_ctx = {
            'cancel_backorder': True,
            'skip_backorder': True,
            'skip_sanity_check': True,
            'skip_sms': True,
        }
        result = picking.with_context(**validate_ctx).button_validate()
        if isinstance(result, dict) and result.get('res_model'):
            # No interactive wizard during import — force done (negative quants are allowed).
            picking.with_context(cancel_backorder=True)._action_done()
        return picking

    def action_cancel_transport(self):
        """Hủy phiếu: nháp → hủy/xóa phiếu kho gắn kèm; hoàn thành → tạo phiếu kho đảo (stock.return.picking)."""
        for rec in self:
            rec._cancel_transport_single()
        return True

    def _cancel_transport_single(self):
        self.ensure_one()
        if self.state == 'cancel':
            return
        if self.state not in ('draft', 'done'):
            raise UserError(_("Chỉ có thể hủy khi phiếu ở trạng thái Nháp hoặc Hoàn thành."))
        if self.state == 'draft':
            self._rr_transport_cancel_draft_with_picking()
        else:
            self._rr_transport_cancel_done_with_reversal()

    def _rr_transport_cancel_draft_with_picking(self):
        self.ensure_one()
        for pick in self.picking_ids.sudo():
            if pick.state == 'done':
                raise UserError(
                    _("Phiếu kho đã hoàn tất nhưng phiếu vận chuyển vẫn là Nháp. Hãy làm mới hoặc liên hệ quản trị.")
                )
            if pick.state != 'cancel':
                pick.action_cancel()
            if pick.exists():
                try:
                    pick.unlink()
                except Exception as ex:
                    _logger.warning("Could not unlink picking %s: %s", pick.id, ex)
        self.write({'state': 'cancel'})

    def _rr_transport_cancel_done_with_reversal(self):
        self.ensure_one()
        candidates = self.picking_ids.sudo().filtered(
            lambda p: p.state == 'done' and not p.return_id
        )
        if not candidates:
            raise UserError(
                _("Phiếu ở trạng thái Hoàn thành cần có ít nhất một phiếu kho gốc đã xác nhận (Done).")
            )
        if len(candidates) > 1:
            raise UserError(
                _("Có nhiều phiếu kho gốc đã hoàn tất. Hãy xử lý thủ công hoặc liên hệ quản trị.")
            )
        pick = candidates[0]
        Wizard = self.env['stock.return.picking'].sudo()
        wizard = Wizard.create({'picking_id': pick.id})
        try:
            new_pid, _pick_type = wizard._create_returns()
        except UserError:
            raise
        except Exception as e:
            _logger.exception("stock.return.picking failed for transport %s", self.id)
            raise UserError(_("Không tạo được phiếu kho đảo: %s") % (e,)) from e
        new_pick = self.env['stock.picking'].browse(new_pid).sudo()
        new_pick.write({'rental_transport_id': self.id})
        self.write({'state': 'cancel'})
        self.message_post(
            body=_(
                "Đã tạo phiếu kho đảo %(name)s. Vui lòng mở phiếu kho và xác nhận (Validate) để cân tồn.",
                name=new_pick.display_name,
            ),
        )

class TransportLine(models.Model):
    _name = "rr.transport.line"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Products assigned to a transport"
    _order = "product_tmpl_id, id"

    transport_id = fields.Many2one('rr.transport', string="Transport", ondelete='cascade', required=True)
    company_id = fields.Many2one(related='transport_id.company_id', store=True, readonly=True, index=True)
    company_group_id = fields.Many2one(related='transport_id.company_group_id', store=True, index=True,
                                       readonly=True)
    rental_contract_id = fields.Many2one(related="transport_id.rental_contract_id", store=True)
    start_rental_or_return_date = fields.Date(related="transport_id.start_rental_or_return_date", store=True)
    product_id = fields.Many2one('product.product', string="Product", required=True, tracking=True)
    product_tmpl_id = fields.Many2one(
        related='product_id.product_tmpl_id',
        store=True,
        index=True,
    )
    uom_id = fields.Many2one(
        "uom.uom",
        string="ĐVT (kho / mẫu)",
        related="product_id.uom_id",
        store=True,
        help="Đơn vị logistics (mẫu). Phiếu kho dùng trường này.",
    )
    staff_display_uom_id = fields.Many2one(
        "uom.uom",
        string="Đơn vị hiển thị",
        compute="_compute_staff_display_uom_id",
        store=True,
        readonly=True,
    )
    qty = fields.Integer(string="Quantity", default=1, tracking=True)
    non_billable_qty = fields.Integer(
        string="SL chuyển dư (không tính tiền)",
        default=0,
        tracking=True,
        help="Phần số lượng giao/trả nhưng KHÔNG tính tiền thuê (ví dụ chuyển dư cho khách). "
             "Vẫn xuất/nhập kho đủ số lượng vật lý, nhưng bảng thanh toán chỉ tính phần còn lại.",
    )
    billable_qty = fields.Integer(
        string="SL tính tiền",
        compute="_compute_billable_qty",
        store=True,
        help="Số lượng dùng để tính tiền thuê = Quantity − SL chuyển dư.",
    )
    transport_type = fields.Selection(
        related="transport_id.type",
        string="Loại phiếu",
        store=True,
    )
    damage_ratio = fields.Selection(
        [
            ('100', '100%'),
            ('50', '50%'),
            ('30', '30%'),
            ('15', '15%'),
        ],
        string="% Đền bù",
        default='100',
        tracking=True,
        help="Tỉ lệ hỏng/đền bù của sản phẩm (chỉ dùng cho phiếu Đền bù). "
             "100% = mất/hỏng hoàn toàn (không nhập lại kho).",
    )
    fine_amount = fields.Float(
        string="Tổng tiền phạt",
        default=0.0,
        tracking=True,
        help="Tiền đền bù = Số lượng × giá đền bù 1 sản phẩm × % đền bù. "
             "Mặc định tính tự động, cho phép nhân viên sửa.",
    )
    name = fields.Char(string="Description")

    # No contract lock enforcement here; only rental.contract base info is locked.

    @api.depends("qty", "non_billable_qty")
    def _compute_billable_qty(self):
        for line in self:
            line.billable_qty = (line.qty or 0) - (line.non_billable_qty or 0)

    def _damage_ratio_value(self):
        """Tỉ lệ hỏng dạng số (0-100). Mặc định 100 nếu chưa đặt."""
        self.ensure_one()
        return int(self.damage_ratio) if self.damage_ratio else 100

    def _compensation_returns_to_stock(self):
        """Dòng đền bù còn nhập lại kho khi tỉ lệ hỏng < 100%."""
        self.ensure_one()
        if self.transport_id.type != 'compensation':
            return True
        return self._damage_ratio_value() < 100

    @api.onchange('product_id', 'qty', 'damage_ratio', 'transport_type')
    def _onchange_compensation_fine_amount(self):
        for line in self:
            if line.transport_id.type != 'compensation':
                continue
            ratio = line._damage_ratio_value() / 100.0
            price = line.product_id.compensation_price or 0.0
            line.fine_amount = (line.qty or 0) * price * ratio

    @api.constrains("qty", "non_billable_qty")
    def _check_non_billable_qty(self):
        for line in self:
            if line.non_billable_qty < 0:
                raise ValidationError(_("SL chuyển dư không được âm."))
            if line.non_billable_qty > line.qty:
                raise ValidationError(
                    _("SL chuyển dư (%(nb)s) không được lớn hơn số lượng (%(qty)s).") % {
                        "nb": line.non_billable_qty,
                        "qty": line.qty,
                    }
                )

    @api.depends(
        "product_id",
        "product_id.staff_display_uom_id",
        "product_id.uom_id",
    )
    def _compute_staff_display_uom_id(self):
        for line in self:
            if line.product_id:
                line.staff_display_uom_id = line.product_id._get_staff_display_uom()
            else:
                line.staff_display_uom_id = False


class TransportTruck(models.Model):
    _name = 'transport.truck'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'mc.group.mixin']
    _rec_name = 'plate'

    name = fields.Char(string='Name', tracking=True)
    plate = fields.Char(string='Plate', tracking=True)


#
# class PriceList(models.Model):
#     _name = "rr.price.list"
#     _description = "Price list"
#
#     start_date = fields.Date(string="Start date")
#     end_date = fields.Date(string="Start date")


# class TransportLine(models.Model):
#     _name = "rr.price.list.line"
#     _description = "Price list line"
#
#     price_list_id = fields.Many2one('rr.price.list', string="Price list", ondelete='cascade', required=True)
#     product_id = fields.Many2one('product.product', string="Product", required=True)
#     uom_id = fields.Many2one('uom.uom', string="UoM", related='product_id.uom_id', store=True)
#     qty = fields.Integer(string="Quantity", default=1)
#     name = fields.Char(string="Description")



# class TransportDriver(models.Model):
#     _name = "rr.transport.driver"
#     _description = "Driver who transport product."
#
#     name = fields.Char(string='Name')
#     driver_name =
#     phone = fields.Char(string='Phone')
#     plate = fields.Char(string='Plate')

