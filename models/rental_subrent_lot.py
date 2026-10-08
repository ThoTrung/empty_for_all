# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare, float_is_zero


class RentalSubrentLot(models.Model):
    _name = "rental.subrent.lot"
    _description = "Lô sản phẩm thuê ngoài"
    _inherit = ["mc.group.mixin", "mail.thread", "mail.activity.mixin"]
    _order = "id desc"
    _rec_name = "name"

    name = fields.Char(
        string="Mã lô",
        required=True,
        copy=False,
        default=lambda self: _("New"),
        tracking=True,
        index=True,
    )
    subrent_contract_id = fields.Many2one(
        "rental.subrent.contract",
        string="HĐ thuê ngoài",
        required=True,
        ondelete="restrict",
        tracking=True,
        index=True,
    )
    supplier_id = fields.Many2one(
        related="subrent_contract_id.supplier_id",
        store=True,
        readonly=True,
        index=True,
    )
    product_id = fields.Many2one(
        "product.product",
        string="Sản phẩm",
        required=True,
        tracking=True,
        index=True,
    )
    product_tmpl_id = fields.Many2one(
        related="product_id.product_tmpl_id",
        store=True,
        readonly=True,
        index=True,
    )
    stock_flow = fields.Selection(
        [
            ("into_stock", "Về kho tạm"),
            ("pass_through", "Giao thẳng công trình"),
        ],
        string="Cách nhập",
        required=True,
        default="into_stock",
        tracking=True,
        index=True,
    )
    cost_unit = fields.Float(
        string="Đơn giá NCC / tháng",
        digits="Product Price",
        tracking=True,
    )
    minimum_rental_months = fields.Float(
        string="Tháng tối thiểu NCC",
        default=0.0,
    )
    date_start = fields.Date(string="Ngày bắt đầu thuê NCC", tracking=True, index=True)
    date_expected_return = fields.Date(string="Ngày dự kiến trả NCC", tracking=True)
    date_end = fields.Date(string="Ngày đóng (trả NCC / hỏng)", tracking=True)
    idle_warn_days = fields.Integer(
        string="Cảnh báo idle (ngày)",
        default=3,
        help="Số ngày nằm kho thuê ngoài liên tục trước khi cảnh báo.",
    )

    receipt_id = fields.Many2one(
        "rental.subrent.receipt",
        string="Phiếu nhận",
        ondelete="set null",
        index=True,
        copy=False,
    )
    ledger_ids = fields.One2many("rental.subrent.ledger", "lot_id", string="Sổ cái")

    qty_received = fields.Float(
        string="SL nhận",
        compute="_compute_qty_buckets",
        store=True,
        digits="Product Unit of Measure",
    )
    qty_at_subrent_wh = fields.Float(
        string="SL tại kho thuê ngoài",
        compute="_compute_qty_buckets",
        store=True,
        digits="Product Unit of Measure",
    )
    qty_on_customer = fields.Float(
        string="SL đang ở công trình",
        compute="_compute_qty_buckets",
        store=True,
        digits="Product Unit of Measure",
    )
    qty_returned_supplier = fields.Float(
        string="SL đã trả NCC",
        compute="_compute_qty_buckets",
        store=True,
        digits="Product Unit of Measure",
    )
    qty_damaged = fields.Float(
        string="SL hỏng",
        compute="_compute_qty_buckets",
        store=True,
        digits="Product Unit of Measure",
    )
    state = fields.Selection(
        [
            ("open", "Mở"),
            ("partial", "Một phần"),
            ("closed", "Đã đóng"),
        ],
        compute="_compute_qty_buckets",
        store=True,
        index=True,
    )
    location_summary = fields.Char(
        string="Đang ở (xô)",
        compute="_compute_location_summary",
    )
    days_in_possession = fields.Integer(
        string="Số ngày đang giữ",
        compute="_compute_possession_idle",
    )
    days_idle = fields.Integer(
        string="Số ngày idle (ước tính)",
        compute="_compute_possession_idle",
    )
    is_idle_warning = fields.Boolean(compute="_compute_possession_idle")
    is_due_return = fields.Boolean(compute="_compute_possession_idle")
    current_construction_label = fields.Char(
        string="Công trình gần nhất",
        compute="_compute_current_construction",
    )

    @api.model_create_multi
    def create(self, vals_list):
        ContractLine = self.env["rental.subrent.contract.line"]
        for vals in vals_list:
            if vals.get("name", _("New")) in (False, _("New"), "New"):
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code("rental.subrent.lot")
                    or _("TN/LÔ")
                )
            if not vals.get("cost_unit") and vals.get("subrent_contract_id") and vals.get("product_id"):
                product = self.env["product.product"].browse(vals["product_id"])
                line = ContractLine.search([
                    ("contract_id", "=", vals["subrent_contract_id"]),
                    ("product_tmpl_id", "=", product.product_tmpl_id.id),
                ], limit=1)
                if line:
                    vals.setdefault("cost_unit", line.cost_unit)
                    vals.setdefault("minimum_rental_months", line.minimum_rental_months)
        return super().create(vals_list)

    def write(self, vals):
        protected = {
            "qty_received",
            "qty_at_subrent_wh",
            "qty_on_customer",
            "qty_returned_supplier",
            "qty_damaged",
            "state",
        }
        if protected.intersection(vals) and not self.env.context.get("rental_subrent_recompute_qty"):
            raise UserError(_("Số lượng lô được tính từ sổ cái — không sửa tay."))
        return super().write(vals)

    def _recompute_qty_fields(self):
        self.with_context(rental_subrent_recompute_qty=True)._compute_qty_buckets()

    @api.depends("ledger_ids", "ledger_ids.move_type", "ledger_ids.qty")
    def _compute_qty_buckets(self):
        for lot in self:
            recv = at_wh = on_cust = ret_sup = dmg = 0.0
            for line in lot.ledger_ids:
                q = line.qty
                mt = line.move_type
                if mt == "receive":
                    recv += q
                    if lot.stock_flow == "into_stock":
                        at_wh += q
                    else:
                        # pass_through receive is paired with deliver; if only receive, treat as on customer prep
                        at_wh += 0.0
                elif mt == "deliver_customer":
                    if lot.stock_flow == "into_stock":
                        at_wh -= q
                    on_cust += q
                elif mt == "return_customer":
                    on_cust -= q
                    if lot.stock_flow == "into_stock":
                        at_wh += q
                    else:
                        # pass_through: trả khách về NCC
                        ret_sup += q
                elif mt == "return_supplier":
                    ret_sup += q
                    at_wh -= q
                elif mt == "damage":
                    dmg += q
                    on_cust -= q
            for line in lot.ledger_ids.filtered(lambda l: l.move_type == "cancel_reversal"):
                effect = (line.note or "").split("|", 1)[0]
                q = line.qty
                if effect == "undo_deliver":
                    on_cust -= q
                    if lot.stock_flow == "into_stock":
                        at_wh += q
                elif effect == "undo_return_customer":
                    on_cust += q
                    if lot.stock_flow == "into_stock":
                        at_wh -= q
                    else:
                        ret_sup -= q
                elif effect == "undo_receive_passthrough_deliver":
                    on_cust -= q
                    recv -= q
                elif effect == "undo_damage":
                    dmg -= q
                    on_cust += q

            prec = self.env["decimal.precision"].precision_get("Product Unit of Measure")
            lot.qty_received = recv
            lot.qty_at_subrent_wh = at_wh
            lot.qty_on_customer = on_cust
            lot.qty_returned_supplier = ret_sup
            lot.qty_damaged = dmg

            open_qty = recv - ret_sup - dmg
            if float_is_zero(open_qty, precision_digits=prec) and recv > 0:
                lot.state = "closed"
            elif ret_sup or dmg or (on_cust and at_wh):
                lot.state = "partial" if not float_is_zero(open_qty, precision_digits=prec) else "closed"
            elif float_compare(ret_sup + dmg, 0.0, precision_digits=prec) > 0 and float_compare(
                open_qty, 0.0, precision_digits=prec
            ) > 0:
                lot.state = "partial"
            else:
                lot.state = "open" if float_compare(open_qty, 0.0, precision_digits=prec) > 0 else "closed"

    def _compute_location_summary(self):
        for lot in self:
            parts = []
            if lot.qty_at_subrent_wh:
                parts.append(_("Kho TN: %s") % lot.qty_at_subrent_wh)
            if lot.qty_on_customer:
                parts.append(_("CT: %s") % lot.qty_on_customer)
            if lot.qty_returned_supplier:
                parts.append(_("Trả NCC: %s") % lot.qty_returned_supplier)
            if lot.qty_damaged:
                parts.append(_("Hỏng: %s") % lot.qty_damaged)
            lot.location_summary = " | ".join(parts) if parts else _("(trống)")

    def _compute_possession_idle(self):
        today = fields.Date.context_today(self)
        for lot in self:
            start = lot.date_start
            end = lot.date_end or today
            if start and end and end >= start:
                lot.days_in_possession = (end - start).days + 1
            else:
                lot.days_in_possession = 0
            # Approximate idle: possession days minus on-customer days from ledger spans
            on_cust_days = lot._estimate_on_customer_days(start, end)
            idle = max(0, lot.days_in_possession - on_cust_days)
            lot.days_idle = idle
            lot.is_idle_warning = bool(
                lot.qty_at_subrent_wh
                and not lot.qty_on_customer
                and idle >= (lot.idle_warn_days or 3)
                and lot.state != "closed"
            )
            lot.is_due_return = bool(
                lot.date_expected_return
                and lot.date_expected_return <= today
                and lot.state != "closed"
            )

    def _estimate_on_customer_days(self, start, end):
        """Rough on-customer day count from deliver/return ledger (FIFO per unit ignored — qty-weighted)."""
        self.ensure_one()
        if not start or not end:
            return 0
        events = []
        for line in self.ledger_ids.sorted(lambda l: (l.date, l.id)):
            if line.move_type == "deliver_customer":
                events.append((line.date, line.qty))
            elif line.move_type == "return_customer":
                events.append((line.date, -line.qty))
            elif line.move_type == "damage":
                events.append((line.date, -line.qty))
            elif line.move_type == "cancel_reversal" and (line.note or "").startswith("undo_deliver"):
                events.append((line.date, -line.qty))
            elif line.move_type == "cancel_reversal" and (line.note or "").startswith(
                "undo_return_customer"
            ):
                events.append((line.date, line.qty))
        # Expand to daily open qty — capped for performance
        if not events:
            return 0
        open_qty = 0.0
        days = 0
        d = start
        ev_i = 0
        events = sorted(events, key=lambda e: e[0] or start)
        while d <= end:
            while ev_i < len(events) and events[ev_i][0] and events[ev_i][0] <= d:
                open_qty += events[ev_i][1]
                ev_i += 1
            if open_qty > 0:
                days += 1
            d += timedelta(days=1)
            if days > 3660:
                break
        return days

    def _compute_current_construction(self):
        for lot in self:
            lines = lot.ledger_ids.filtered(
                lambda l: l.move_type == "deliver_customer" and l.transport_id
            ).sorted(lambda l: (l.date, l.id), reverse=True)
            label = ""
            for led in lines:
                contract = led.transport_id.rental_contract_id
                if contract and lot.qty_on_customer:
                    work = contract.construction_work_id
                    label = work.display_name if work else contract.display_name
                    break
            lot.current_construction_label = label

    def _assert_can_deliver(self, qty):
        self.ensure_one()
        prec = self.env["decimal.precision"].precision_get("Product Unit of Measure")
        available = self.qty_at_subrent_wh if self.stock_flow == "into_stock" else 0.0
        if self.stock_flow == "pass_through":
            # dropship: available = received - already on customer - returned - damaged
            available = self.qty_received - self.qty_on_customer - self.qty_returned_supplier - self.qty_damaged
            # For pure dropship deliver that creates receive+deliver together, check happens after
        if float_compare(qty, available, precision_digits=prec) > 0 and self.stock_flow == "into_stock":
            raise ValidationError(
                _("Lô %(lot)s chỉ còn %(avail)s tại kho thuê ngoài (yêu cầu %(qty)s).")
                % {"lot": self.name, "avail": available, "qty": qty}
            )

    def _assert_can_return_from_customer(self, qty):
        self.ensure_one()
        prec = self.env["decimal.precision"].precision_get("Product Unit of Measure")
        if float_compare(qty, self.qty_on_customer, precision_digits=prec) > 0:
            raise ValidationError(
                _("Lô %(lot)s chỉ còn %(avail)s ở công trình (yêu cầu trả %(qty)s).")
                % {"lot": self.name, "avail": self.qty_on_customer, "qty": qty}
            )

    def _assert_can_return_to_supplier(self, qty):
        self.ensure_one()
        prec = self.env["decimal.precision"].precision_get("Product Unit of Measure")
        if float_compare(self.qty_on_customer, 0.0, precision_digits=prec) > 0:
            raise UserError(
                _("Lô %(lot)s còn %(qty)s ở công trình — thu về kho hoặc trả thẳng NCC qua VC trước.")
                % {"lot": self.name, "qty": self.qty_on_customer}
            )
        if float_compare(qty, self.qty_at_subrent_wh, precision_digits=prec) > 0:
            raise ValidationError(
                _("Lô %(lot)s chỉ còn %(avail)s tại kho thuê ngoài.")
                % {"lot": self.name, "avail": self.qty_at_subrent_wh}
            )

    def action_open_ledger(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Sổ cái"),
            "res_model": "rental.subrent.ledger",
            "view_mode": "tree,form",
            "domain": [("lot_id", "=", self.id)],
        }
