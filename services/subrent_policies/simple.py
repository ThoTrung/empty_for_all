# -*- coding: utf-8 -*-
from odoo import _
from odoo.exceptions import ValidationError
from odoo.tools.float_utils import float_compare

from .base import AbstractSubrentPolicy
from .registry import register
from . import stock_helpers as sh


@register
class SimpleStockPolicy(AbstractSubrentPolicy):
    code = "simple"
    label = "Đơn giản — nhập kho mình"
    capabilities = frozenset({
        "tracks_qty_open",
        "monthly_payable_from_open",
        "allows_return_when_surplus",
    })

    def on_receipt_confirm(self, receipt):
        for line in receipt.line_ids:
            if line.qty <= 0:
                raise ValidationError(_("Số lượng nhận phải > 0."))
            cline = receipt._contract_line_for_product(line.product_id)
            cline.qty_received = (cline.qty_received or 0.0) + line.qty
        dest = sh.get_owned_stock_location(receipt.company_id)
        picking = sh.create_incoming_picking(receipt, dest)
        receipt.picking_ids = [(4, picking.id)]
        sh.validate_picking(picking)

    def on_return_confirm(self, return_doc):
        company = return_doc.company_id
        stock_loc = sh.get_owned_stock_location(company)
        for line in return_doc.line_ids:
            if line.qty <= 0:
                raise ValidationError(_("Số lượng trả phải > 0."))
            if not line.product_id:
                raise ValidationError(_("Chọn sản phẩm trên dòng trả."))
            cline = return_doc.subrent_contract_id.line_ids.filtered(
                lambda l, p=line.product_id: l.product_tmpl_id == p.product_tmpl_id
            )[:1]
            if not cline:
                raise ValidationError(
                    _("Sản phẩm %(p)s không có trên HĐ.") % {"p": line.product_id.display_name}
                )
            open_qty = cline.qty_open
            prec = return_doc.env["decimal.precision"].precision_get("Product Unit of Measure")
            if float_compare(line.qty, open_qty, precision_digits=prec) > 0:
                raise ValidationError(
                    _("Chỉ còn %(open)s đang thuê NCC (yêu cầu trả %(qty)s).")
                    % {"open": open_qty, "qty": line.qty}
                )
            onhand = sh.product_onhand_at_location(
                return_doc.env, line.product_id, stock_loc, company
            )
            if float_compare(line.qty, onhand, precision_digits=prec) > 0:
                raise ValidationError(
                    _("Tồn kho dư chỉ còn %(oh)s (yêu cầu trả %(qty)s).")
                    % {"oh": onhand, "qty": line.qty}
                )
        picking = sh.create_outgoing_picking(return_doc, return_doc.line_ids, stock_loc)
        return_doc.picking_ids = [(4, picking.id)]
        sh.validate_picking(picking)
        for line in return_doc.line_ids:
            cline = return_doc.subrent_contract_id.line_ids.filtered(
                lambda l, p=line.product_id: l.product_tmpl_id == p.product_tmpl_id
            )[:1]
            cline.qty_returned = (cline.qty_returned or 0.0) + line.qty

    def compute_monthly_payable(self, contract, date_from, date_to):
        # MVP: qty_open × cost_unit (monthly rate) as of now / end of period
        rows = []
        for line in contract.line_ids:
            qty = line.qty_open
            if qty <= 0:
                continue
            amount = qty * (line.cost_unit or 0.0)
            rows.append({
                "contract_line": line,
                "product_tmpl_id": line.product_tmpl_id.id,
                "qty_open": qty,
                "cost_unit": line.cost_unit,
                "amount": amount,
            })
        return rows
