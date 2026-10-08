# -*- coding: utf-8 -*-
"""Pass-through / dropship policy."""
from odoo import _
from odoo.exceptions import UserError, ValidationError

from .base import AbstractSubrentPolicy
from .registry import register
from .tracked import TrackedLotPolicy


@register
class PassThroughPolicy(AbstractSubrentPolicy):
    code = "pass_through"
    label = "Giao thẳng công trình"
    capabilities = frozenset({
        "uses_lots",
        "links_transport_source",
    })

    def __init__(self):
        self._tracked = TrackedLotPolicy()

    def on_receipt_confirm(self, receipt):
        # Allow creating empty pass_through lots without stock move (prep for VC)
        if receipt.stock_flow != "pass_through":
            receipt.stock_flow = "pass_through"
        Lot = receipt.env["rental.subrent.lot"]
        for line in receipt.line_ids:
            if line.qty <= 0:
                raise ValidationError(_("Số lượng phải > 0."))
            cline = receipt._contract_line_for_product(line.product_id)
            lot = Lot.create({
                "subrent_contract_id": receipt.subrent_contract_id.id,
                "product_id": line.product_id.id,
                "stock_flow": "pass_through",
                "cost_unit": cline.cost_unit,
                "minimum_rental_months": cline.minimum_rental_months,
                "date_start": receipt.date,
                "date_expected_return": receipt.subrent_contract_id.date_end,
                "receipt_id": receipt.id,
                "company_id": receipt.company_id.id,
            })
            line.lot_id = lot.id
            # No receive ledger yet — created on VC deliver (dropship)

    def on_return_confirm(self, return_doc):
        raise UserError(
            _("Chế độ giao thẳng: trả NCC qua phiếu vận chuyển khách (trả hàng), không dùng phiếu Trả NCC từ kho.")
        )

    def on_transport_done(self, transport):
        self._tracked.on_transport_done(transport)

    def on_transport_cancel(self, transport):
        self._tracked.on_transport_cancel(transport)

    def picking_locations(self, transport):
        return self._tracked.picking_locations(transport)

    def compute_monthly_payable(self, contract, date_from, date_to):
        return []
