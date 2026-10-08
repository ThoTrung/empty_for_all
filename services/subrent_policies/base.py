# -*- coding: utf-8 -*-
"""Abstract subrent management policy (DEC-S07)."""
from abc import ABC, abstractmethod


class AbstractSubrentPolicy(ABC):
    code = None
    label = None
    capabilities = frozenset()

    def has(self, cap):
        return cap in self.capabilities

    @abstractmethod
    def on_receipt_confirm(self, receipt):
        """Confirm NCC receipt: stock + obligation/lots."""

    @abstractmethod
    def on_return_confirm(self, return_doc):
        """Confirm return to NCC."""

    def on_transport_done(self, transport):
        """Hook when customer transport becomes done. Default no-op."""

    def on_transport_cancel(self, transport):
        """Hook when customer transport cancelled. Default no-op."""

    def picking_locations(self, transport):
        """Return (src, dest) or None to keep default owned locations."""
        return None

    def compute_monthly_payable(self, contract, date_from, date_to):
        """Return list of dicts: product/line, qty_open, cost_unit, amount."""
        return []
