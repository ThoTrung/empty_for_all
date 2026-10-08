# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from odoo.addons.rental_subrent.services.subrent_policies import get_policy


class Transport(models.Model):
    _inherit = "rr.transport"

    source_type = fields.Selection(
        [
            ("owned", "Tự có"),
            ("subrent", "Thuê ngoài"),
        ],
        string="Nguồn hàng",
        default="owned",
        required=True,
        tracking=True,
        index=True,
        help="Một phiếu vận chuyển chỉ một nguồn (DEC-S02). Dùng với HĐ NCC chế độ truy xuất lô / giao thẳng.",
    )

    @api.constrains("source_type", "transport_line_ids", "state")
    def _check_subrent_lines(self):
        for rec in self:
            if rec.source_type != "subrent" or rec.state not in ("done",):
                continue
            missing_all = rec.transport_line_ids.filtered(lambda l: not l.subrent_lot_id)
            if missing_all:
                raise ValidationError(
                    _("Nguồn Thuê ngoài: mọi dòng phải chọn lô thuê ngoài.")
                )
            for line in rec.transport_line_ids:
                if line.subrent_lot_id and line.product_id != line.subrent_lot_id.product_id:
                    raise ValidationError(
                        _("Dòng %(p)s không khớp sản phẩm của lô %(lot)s.")
                        % {"p": line.product_id.display_name, "lot": line.subrent_lot_id.name}
                    )

    def action_create_pickings(self):
        for rec in self:
            if rec.source_type == "subrent":
                if not rec.transport_line_ids:
                    raise UserError(_("Thêm dòng sản phẩm."))
                missing = rec.transport_line_ids.filtered(lambda l: not l.subrent_lot_id)
                if missing:
                    raise UserError(_("Nguồn Thuê ngoài: chọn lô trên mọi dòng trước khi tạo phiếu kho."))
                for line in rec.transport_line_ids:
                    if line.product_id != line.subrent_lot_id.product_id:
                        raise UserError(
                            _("Sản phẩm không khớp lô %(lot)s.") % {"lot": line.subrent_lot_id.name}
                        )
                flows = set(rec.transport_line_ids.mapped("subrent_lot_id.stock_flow"))
                if len(flows) > 1:
                    raise UserError(_("Không trộn kho tạm và giao thẳng trên cùng phiếu."))
        return super().action_create_pickings()

    def _rental_picking_locations(self):
        self.ensure_one()
        if self.source_type != "subrent":
            return super()._rental_picking_locations()
        lots = self.transport_line_ids.mapped("subrent_lot_id")
        contracts = lots.mapped("subrent_contract_id")
        if not contracts:
            return super()._rental_picking_locations()
        # One policy per transport (all lots same contract policy expected)
        policy = contracts[0].get_subrent_policy()
        locs = policy.picking_locations(self)
        if locs:
            return locs
        return super()._rental_picking_locations()

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records.filtered(
            lambda t: t.state == "done" and t.source_type == "subrent"
        )._rental_subrent_on_transport_done()
        return records

    def write(self, vals):
        res = super().write(vals)
        if vals.get("state") == "done":
            self._rental_subrent_on_transport_done()
        if vals.get("state") == "cancel":
            self._rental_subrent_on_transport_cancel()
        return res

    def _rental_subrent_policies_for_transport(self):
        self.ensure_one()
        lots = self.transport_line_ids.mapped("subrent_lot_id")
        policies = []
        for contract in lots.mapped("subrent_contract_id"):
            policies.append(contract.get_subrent_policy())
        if not policies and self.source_type == "subrent":
            # Fallback tracked for legacy lots without going through contract
            policies.append(get_policy("tracked"))
        return policies

    def _rental_subrent_on_transport_done(self):
        for rec in self.filtered(lambda t: t.source_type == "subrent"):
            for policy in rec._rental_subrent_policies_for_transport():
                policy.on_transport_done(rec)

    def _rental_subrent_on_transport_cancel(self):
        for rec in self.filtered(lambda t: t.source_type == "subrent"):
            for policy in rec._rental_subrent_policies_for_transport():
                policy.on_transport_cancel(rec)

    def _rental_subrent_tracked_transport_done(self):
        """Ledger updates for tracked / pass_through lots (called by policies)."""
        Ledger = self.env["rental.subrent.ledger"]
        for rec in self:
            existing = Ledger.search([("transport_id", "=", rec.id)], limit=1)
            if existing:
                continue
            for line in rec.transport_line_ids:
                if not line.subrent_lot_id or line.qty <= 0:
                    continue
                lot = line.subrent_lot_id
                if rec.type == "delivery":
                    if lot.stock_flow == "pass_through" and not lot.ledger_ids.filtered(
                        lambda l: l.move_type == "receive"
                    ):
                        Ledger.create({
                            "lot_id": lot.id,
                            "move_type": "receive",
                            "qty": line.qty,
                            "date": rec.start_rental_or_return_date,
                            "transport_id": rec.id,
                            "transport_line_id": line.id,
                            "note": "dropship_receive",
                        })
                        if not lot.date_start:
                            lot.date_start = rec.start_rental_or_return_date
                    else:
                        lot._assert_can_deliver(line.qty)
                    Ledger.create({
                        "lot_id": lot.id,
                        "move_type": "deliver_customer",
                        "qty": line.qty,
                        "date": rec.start_rental_or_return_date,
                        "transport_id": rec.id,
                        "transport_line_id": line.id,
                    })
                elif rec.type == "return":
                    lot._assert_can_return_from_customer(line.qty)
                    Ledger.create({
                        "lot_id": lot.id,
                        "move_type": "return_customer",
                        "qty": line.qty,
                        "date": rec.start_rental_or_return_date,
                        "transport_id": rec.id,
                        "transport_line_id": line.id,
                    })
                    if (
                        lot.stock_flow == "pass_through"
                        and lot.qty_on_customer <= 0
                        and lot.qty_at_subrent_wh <= 0
                    ):
                        lot.date_end = rec.start_rental_or_return_date
                elif rec.type == "compensation":
                    lot._assert_can_return_from_customer(line.qty)
                    if line._compensation_returns_to_stock():
                        Ledger.create({
                            "lot_id": lot.id,
                            "move_type": "return_customer",
                            "qty": line.qty,
                            "date": rec.start_rental_or_return_date,
                            "transport_id": rec.id,
                            "transport_line_id": line.id,
                        })
                    else:
                        Ledger.create({
                            "lot_id": lot.id,
                            "move_type": "damage",
                            "qty": line.qty,
                            "date": rec.start_rental_or_return_date,
                            "transport_id": rec.id,
                            "transport_line_id": line.id,
                        })
                        if lot.qty_on_customer <= 0 and lot.qty_at_subrent_wh <= 0:
                            lot.date_end = rec.start_rental_or_return_date

    def _rental_subrent_tracked_transport_cancel(self):
        Ledger = self.env["rental.subrent.ledger"]
        for rec in self:
            ledgers = Ledger.search([
                ("transport_id", "=", rec.id),
                ("move_type", "!=", "cancel_reversal"),
            ])
            if not ledgers:
                continue
            already = Ledger.search([
                ("transport_id", "=", rec.id),
                ("move_type", "=", "cancel_reversal"),
            ], limit=1)
            if already:
                continue
            for led in ledgers:
                if led.move_type == "deliver_customer":
                    effect = "undo_deliver"
                elif led.move_type == "return_customer":
                    effect = "undo_return_customer"
                elif led.move_type == "receive" and (led.note or "") == "dropship_receive":
                    effect = "undo_receive_passthrough_deliver"
                elif led.move_type == "damage":
                    effect = "undo_damage"
                else:
                    continue
                Ledger.create({
                    "lot_id": led.lot_id.id,
                    "move_type": "cancel_reversal",
                    "qty": led.qty,
                    "date": fields.Date.context_today(self),
                    "transport_id": rec.id,
                    "transport_line_id": led.transport_line_id.id,
                    "note": "%s|%s" % (effect, led.id),
                })


class TransportLine(models.Model):
    _inherit = "rr.transport.line"

    subrent_lot_id = fields.Many2one(
        "rental.subrent.lot",
        string="Lô thuê ngoài",
        ondelete="restrict",
        index=True,
        domain="[('product_id', '=', product_id), ('state', '!=', 'closed')]",
    )

    def _copy_line_vals(self):
        # Nghiệp vụ: phiếu nhân bản phải chọn lại lô thuê ngoài.
        vals = super()._copy_line_vals()
        vals["subrent_lot_id"] = False
        return vals

    @api.onchange("product_id")
    def _onchange_product_clear_subrent_lot(self):
        if self.subrent_lot_id and self.product_id != self.subrent_lot_id.product_id:
            self.subrent_lot_id = False
