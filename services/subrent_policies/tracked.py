# -*- coding: utf-8 -*-
"""Tracked lot + WH/Subrent policy — wraps existing ledger behavior."""
from odoo import _
from odoo.exceptions import UserError, ValidationError

from .base import AbstractSubrentPolicy
from .registry import register
from . import stock_helpers as sh


@register
class TrackedLotPolicy(AbstractSubrentPolicy):
    code = "tracked"
    label = "Truy xuất lô + kho thuê ngoài"
    capabilities = frozenset({
        "uses_lots",
        "uses_subrent_wh",
        "links_transport_source",
    })

    def on_receipt_confirm(self, receipt):
        if receipt.stock_flow == "pass_through":
            raise UserError(
                _("HĐ chế độ Truy xuất lô: dùng «Về kho tạm». Giao thẳng chọn policy Giao thẳng.")
            )
        self._create_lots_and_ledger(receipt, stock_flow="into_stock")
        dest = receipt.company_id._rental_subrent_stock_location()
        picking = sh.create_incoming_picking(receipt, dest)
        receipt.picking_ids = [(4, picking.id)]
        sh.validate_picking(picking)

    def _create_lots_and_ledger(self, receipt, stock_flow):
        Lot = receipt.env["rental.subrent.lot"]
        Ledger = receipt.env["rental.subrent.ledger"]
        for line in receipt.line_ids:
            if line.qty <= 0:
                raise ValidationError(_("Số lượng nhận phải > 0."))
            cline = receipt._contract_line_for_product(line.product_id)
            lot = Lot.create({
                "subrent_contract_id": receipt.subrent_contract_id.id,
                "product_id": line.product_id.id,
                "stock_flow": stock_flow,
                "cost_unit": cline.cost_unit,
                "minimum_rental_months": cline.minimum_rental_months,
                "date_start": receipt.date,
                "date_expected_return": receipt.subrent_contract_id.date_end,
                "receipt_id": receipt.id,
                "company_id": receipt.company_id.id,
            })
            line.lot_id = lot.id
            Ledger.create({
                "lot_id": lot.id,
                "move_type": "receive",
                "qty": line.qty,
                "date": receipt.date,
                "receipt_id": receipt.id,
            })

    def on_return_confirm(self, return_doc):
        for line in return_doc.line_ids:
            if line.qty <= 0:
                raise ValidationError(_("Số lượng trả phải > 0."))
            if not line.lot_id:
                raise ValidationError(_("Chế độ truy xuất lô: chọn lô trên mọi dòng trả."))
            if line.lot_id.subrent_contract_id != return_doc.subrent_contract_id:
                raise ValidationError(_("Lô không thuộc HĐ đã chọn."))
            line.lot_id._assert_can_return_to_supplier(line.qty)
        into_stock_lines = return_doc.line_ids.filtered(
            lambda l: l.lot_id.stock_flow == "into_stock"
        )
        if into_stock_lines:
            src = return_doc.company_id._rental_subrent_stock_location()
            picking = sh.create_outgoing_picking(return_doc, into_stock_lines, src)
            return_doc.picking_ids = [(4, picking.id)]
            sh.validate_picking(picking)
        Ledger = return_doc.env["rental.subrent.ledger"]
        for line in return_doc.line_ids:
            Ledger.create({
                "lot_id": line.lot_id.id,
                "move_type": "return_supplier",
                "qty": line.qty,
                "date": return_doc.date,
                "return_id": return_doc.id,
            })
            lot = line.lot_id
            if lot.qty_at_subrent_wh <= 0 and lot.qty_on_customer <= 0:
                lot.date_end = return_doc.date

    def on_transport_done(self, transport):
        # Delegates to existing transport helper (keeps one place for ledger rules)
        transport._rental_subrent_tracked_transport_done()

    def on_transport_cancel(self, transport):
        transport._rental_subrent_tracked_transport_cancel()

    def picking_locations(self, transport):
        if transport.source_type != "subrent":
            return None
        company = transport.company_id or transport.rental_contract_id.company_id
        customer = transport._get_partner_customer_location()
        lots = transport.transport_line_ids.mapped("subrent_lot_id")
        flows = set(lots.mapped("stock_flow"))
        if len(flows) > 1:
            raise UserError(
                _("Một phiếu thuê ngoài không được trộn «Về kho tạm» và «Giao thẳng».")
            )
        flow = next(iter(flows)) if flows else "into_stock"
        if transport.type == "delivery":
            if flow == "pass_through":
                src = company._rental_subrent_supplier_location()
            else:
                src = company._rental_subrent_stock_location()
            return src, customer
        if flow == "pass_through":
            dest = company._rental_subrent_supplier_location()
        else:
            dest = company._rental_subrent_stock_location()
        return customer, dest

    def compute_monthly_payable(self, contract, date_from, date_to):
        # Optional later: possession cost from lots. MVP empty for tracked.
        return []
