# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from odoo.addons.rental_subrent.services.subrent_policies import get_policy, selection_list


class RentalSubrentContract(models.Model):
    _name = "rental.subrent.contract"
    _description = "Hợp đồng thuê ngoài (NCC)"
    _inherit = ["mc.group.mixin", "mail.thread", "mail.activity.mixin"]
    _order = "id desc"
    _rec_name = "name"

    name = fields.Char(
        string="Mã HĐ",
        required=True,
        copy=False,
        default=lambda self: _("New"),
        tracking=True,
        index=True,
    )
    supplier_id = fields.Many2one(
        "res.partner",
        string="NCC",
        required=True,
        tracking=True,
        domain="[('is_rental_supplier', '=', True), ('is_company', '=', True)]",
        index=True,
    )
    contract_date = fields.Date(
        string="Ngày hợp đồng",
        tracking=True,
        help="Ngày ký / ghi trên giấy HĐ với NCC (tuỳ chọn).",
    )
    contract_number = fields.Char(
        string="Số HĐ trên giấy",
        tracking=True,
        help="Số hiệu HĐ giấy với NCC (khác mã hệ thống).",
    )
    company_partner_id = fields.Many2one(
        "res.partner",
        string="Đối tác công ty (helper)",
        related="company_id.partner_id",
        store=False,
    )
    supplier_representative_id = fields.Many2one(
        "res.partner",
        string="Đại diện NCC",
        tracking=True,
        domain="[('parent_id', '=', supplier_id)]",
        help="Liên hệ thuộc NCC (parent = NCC).",
    )
    our_representative_id = fields.Many2one(
        "res.partner",
        string="Đại diện bên ta",
        tracking=True,
        domain="[('parent_id', '=', company_partner_id)]",
        help="Liên hệ thuộc công ty mình.",
    )
    policy_code = fields.Selection(
        selection="_selection_policy_code",
        string="Chế độ quản lý",
        required=True,
        default="simple",
        tracking=True,
        index=True,
        help="Đơn giản: nhập kho mình + SL đang thuê NCC. "
             "Truy xuất lô: kho TN + gắn VC. Giao thẳng: dropship.",
    )
    show_obligation_ui = fields.Boolean(compute="_compute_policy_ui_flags")
    show_lot_ui = fields.Boolean(compute="_compute_policy_ui_flags")
    require_transport_lot = fields.Boolean(compute="_compute_policy_ui_flags")
    date_start = fields.Date(string="Ngày bắt đầu", tracking=True)
    date_end = fields.Date(string="Ngày kết thúc dự kiến", tracking=True)
    state = fields.Selection(
        [
            ("draft", "Nháp"),
            ("active", "Đang hiệu lực"),
            ("done", "Hoàn thành"),
            ("cancel", "Hủy"),
        ],
        default="draft",
        required=True,
        tracking=True,
        index=True,
    )
    line_ids = fields.One2many(
        "rental.subrent.contract.line",
        "contract_id",
        string="Dòng sản phẩm",
        copy=True,
    )
    lot_ids = fields.One2many(
        "rental.subrent.lot",
        "subrent_contract_id",
        string="Lô thuê ngoài",
    )
    lot_count = fields.Integer(compute="_compute_lot_count")
    receipt_ids = fields.One2many(
        "rental.subrent.receipt",
        "subrent_contract_id",
        string="Phiếu nhận từ NCC",
    )
    return_ids = fields.One2many(
        "rental.subrent.return",
        "subrent_contract_id",
        string="Phiếu trả NCC",
    )
    qty_open_total = fields.Float(
        string="Tổng SL đang thuê NCC",
        compute="_compute_obligation_totals",
    )
    amount_monthly_estimate = fields.Float(
        string="Tiền/tháng ước tính",
        compute="_compute_obligation_totals",
        groups="rental_subrent.group_rental_subrent_manager",
    )
    note = fields.Text(string="Ghi chú")

    @api.model
    def _selection_policy_code(self):
        try:
            return selection_list()
        except Exception:
            return [
                ("simple", "Đơn giản — nhập kho mình"),
                ("tracked", "Truy xuất lô + kho thuê ngoài"),
                ("pass_through", "Giao thẳng công trình"),
            ]

    def get_subrent_policy(self):
        self.ensure_one()
        return get_policy(self.policy_code or "simple")

    @api.depends("policy_code")
    def _compute_policy_ui_flags(self):
        for rec in self:
            try:
                policy = get_policy(rec.policy_code or "simple")
            except Exception:
                policy = None
            caps = policy.capabilities if policy else frozenset()
            rec.show_obligation_ui = "tracks_qty_open" in caps
            rec.show_lot_ui = "uses_lots" in caps
            rec.require_transport_lot = "links_transport_source" in caps

    @api.depends("lot_ids")
    def _compute_lot_count(self):
        for rec in self:
            rec.lot_count = len(rec.lot_ids)

    @api.depends("line_ids.qty_open", "line_ids.cost_unit", "line_ids.qty_received", "line_ids.qty_returned")
    def _compute_obligation_totals(self):
        for rec in self:
            rec.qty_open_total = sum(rec.line_ids.mapped("qty_open"))
            rec.amount_monthly_estimate = sum(
                (l.qty_open or 0.0) * (l.cost_unit or 0.0) for l in rec.line_ids
            )

    @api.constrains("policy_code")
    def _check_policy_locked(self):
        for rec in self:
            if rec.lot_ids or any(l.qty_received for l in rec.line_ids):
                # Allow same value; block change detected in write
                pass

    def write(self, vals):
        if "policy_code" in vals and not self.env.context.get("rental_subrent_force_policy"):
            for rec in self:
                if rec.lot_ids or any(l.qty_received for l in rec.line_ids):
                    if vals["policy_code"] != rec.policy_code:
                        raise UserError(
                            _("Không đổi chế độ quản lý sau khi đã nhận hàng / tạo lô.")
                        )
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("New")) in (False, _("New"), "New"):
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code("rental.subrent.contract")
                    or _("TN/HĐ")
                )
            vals.setdefault("policy_code", "simple")
        return super().create(vals_list)

    def action_activate(self):
        for rec in self:
            if not rec.line_ids:
                raise UserError(_("Thêm ít nhất một dòng sản phẩm trước khi kích hoạt."))
            rec.state = "active"
        return True

    def action_done(self):
        for rec in self:
            policy = rec.get_subrent_policy()
            if policy.has("uses_lots"):
                open_lots = rec.lot_ids.filtered(lambda l: l.state != "closed")
                if open_lots:
                    raise UserError(
                        _("Còn lô chưa đóng: %(lots)s")
                        % {"lots": ", ".join(open_lots.mapped("name"))}
                    )
            if policy.has("tracks_qty_open") and rec.qty_open_total > 0:
                raise UserError(
                    _("Còn %(q)s đang thuê NCC — trả hết trước khi hoàn thành HĐ.")
                    % {"q": rec.qty_open_total}
                )
        self.write({"state": "done"})
        return True

    def action_cancel(self):
        for rec in self:
            policy = rec.get_subrent_policy()
            if policy.has("uses_lots"):
                open_lots = rec.lot_ids.filtered(lambda l: l.state != "closed")
                if open_lots:
                    raise UserError(_("Không hủy HĐ khi còn lô đang mở."))
            if policy.has("tracks_qty_open") and rec.qty_open_total > 0:
                raise UserError(_("Không hủy HĐ khi còn SL đang thuê NCC."))
        self.write({"state": "cancel"})
        return True

    def action_set_draft(self):
        self.write({"state": "draft"})
        return True

    def action_open_lots(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Lô thuê ngoài"),
            "res_model": "rental.subrent.lot",
            "view_mode": "tree,form",
            "domain": [("subrent_contract_id", "=", self.id)],
            "context": {"default_subrent_contract_id": self.id},
        }


class RentalSubrentContractLine(models.Model):
    _name = "rental.subrent.contract.line"
    _description = "Dòng HĐ thuê ngoài"
    _order = "id"

    contract_id = fields.Many2one(
        "rental.subrent.contract",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(
        related="contract_id.company_id",
        store=True,
        readonly=True,
        index=True,
    )
    product_tmpl_id = fields.Many2one(
        "product.template",
        string="Mẫu sản phẩm",
        required=True,
        domain="[('sale_ok', '=', True)]",
        index=True,
    )
    cost_unit = fields.Float(
        string="Đơn giá thuê NCC / tháng",
        required=True,
        digits="Product Price",
        help="Cùng convention DEC-11: giá tháng; cost/ngày ≈ /30.",
    )
    minimum_rental_months = fields.Float(
        string="Số tháng thuê tối thiểu (NCC)",
        default=0.0,
    )
    qty_received = fields.Float(
        string="SL đã nhận NCC",
        default=0.0,
        digits="Product Unit of Measure",
        copy=False,
        readonly=True,
    )
    qty_returned = fields.Float(
        string="SL đã trả NCC",
        default=0.0,
        digits="Product Unit of Measure",
        copy=False,
        readonly=True,
    )
    qty_open = fields.Float(
        string="SL đang thuê NCC",
        compute="_compute_qty_open",
        store=True,
        digits="Product Unit of Measure",
    )
    amount_monthly_estimate = fields.Float(
        string="Tiền/tháng ước tính",
        compute="_compute_qty_open",
        store=True,
    )
    note = fields.Char(string="Ghi chú")

    @api.depends("qty_received", "qty_returned", "cost_unit")
    def _compute_qty_open(self):
        for line in self:
            line.qty_open = (line.qty_received or 0.0) - (line.qty_returned or 0.0)
            line.amount_monthly_estimate = line.qty_open * (line.cost_unit or 0.0)

    @api.constrains("cost_unit")
    def _check_cost_unit(self):
        for line in self:
            if line.cost_unit < 0:
                raise ValidationError(_("Đơn giá NCC không được âm."))

    @api.constrains("qty_received", "qty_returned")
    def _check_qty_open_non_negative(self):
        for line in self:
            if (line.qty_received or 0.0) - (line.qty_returned or 0.0) < -1e-6:
                raise ValidationError(_("SL trả NCC không được vượt SL đã nhận."))
