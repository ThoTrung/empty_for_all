# -*- coding: utf-8 -*-
"""Init billable_qty = qty for existing transport lines (non_billable_qty defaults to 0)."""


def migrate(cr, version):
    cr.execute(
        """
        UPDATE rr_transport_line
        SET non_billable_qty = COALESCE(non_billable_qty, 0),
            billable_qty = qty - COALESCE(non_billable_qty, 0)
        WHERE billable_qty IS DISTINCT FROM (qty - COALESCE(non_billable_qty, 0))
        """
    )
