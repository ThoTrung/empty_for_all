# -*- coding: utf-8 -*-
"""Reconcile WH/Subrent quants vs open lot buckets."""
from collections import defaultdict


def reconcile_subrent_stock(env, company):
    loc = company._rental_subrent_stock_location()
    Quant = env["stock.quant"].sudo()
    groups = Quant.read_group(
        [
            ("location_id", "child_of", loc.id),
            ("company_id", "=", company.id),
        ],
        ["product_id", "quantity:sum"],
        ["product_id"],
        lazy=False,
    )
    quant_by_product = {
        g["product_id"][0]: g.get("quantity", 0.0)
        for g in groups
        if g.get("product_id")
    }
    lots = env["rental.subrent.lot"].search([
        ("company_id", "=", company.id),
        ("stock_flow", "=", "into_stock"),
        ("state", "!=", "closed"),
    ])
    ledger_by_product = defaultdict(float)
    for lot in lots:
        ledger_by_product[lot.product_id.id] += lot.qty_at_subrent_wh

    product_ids = set(quant_by_product) | set(ledger_by_product)
    diffs = []
    for pid in product_ids:
        q = quant_by_product.get(pid, 0.0)
        l = ledger_by_product.get(pid, 0.0)
        if abs(q - l) > 1e-6:
            diffs.append({
                "product_id": pid,
                "quant_qty": q,
                "ledger_qty": l,
                "difference": q - l,
            })
    return diffs
