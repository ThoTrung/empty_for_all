# -*- coding: utf-8 -*-
"""Staff-facing availability / status helpers for subrent lots."""
from collections import defaultdict

from odoo import fields


def get_subrent_kpis(env, company_ids=None):
    Lot = env["rental.subrent.lot"]
    domain = [("state", "!=", "closed")]
    if company_ids:
        domain.append(("company_id", "in", list(company_ids)))
    lots = Lot.search(domain)
    return {
        "lot_count_open": len(lots),
        "qty_at_subrent_wh": sum(lots.mapped("qty_at_subrent_wh")),
        "qty_on_customer": sum(lots.mapped("qty_on_customer")),
        "idle_lot_count": len(lots.filtered("is_idle_warning")),
        "due_lot_count": len(lots.filtered("is_due_return")),
        "cost_per_day_estimate": sum(
            (lot.cost_unit or 0.0) / 30.0
            for lot in lots
            if (lot.qty_at_subrent_wh or 0) + (lot.qty_on_customer or 0) > 0
        ),
    }


def shortage_for_product(env, product, qty_needed, company):
    """Return owned on-hand, subrent WH qty, and shortage."""
    Location = env["stock.location"].sudo()
    wh = env["stock.warehouse"].sudo().search([("company_id", "=", company.id)], limit=1)
    owned_loc_ids = []
    if wh and wh.lot_stock_id:
        owned_loc_ids = Location.search([
            ("id", "child_of", wh.lot_stock_id.id),
            ("usage", "=", "internal"),
            ("is_rental_subrent_stock", "=", False),
        ]).ids
    Quant = env["stock.quant"].sudo()
    owned = 0.0
    if owned_loc_ids:
        groups = Quant.read_group(
            [
                ("product_id", "=", product.id),
                ("location_id", "in", owned_loc_ids),
            ],
            ["quantity:sum"],
            [],
        )
        owned = groups[0].get("quantity", 0.0) if groups else 0.0

    lots = env["rental.subrent.lot"].search([
        ("product_id", "=", product.id),
        ("company_id", "=", company.id),
        ("state", "!=", "closed"),
        ("qty_at_subrent_wh", ">", 0),
    ])
    subrent_wh = sum(lots.mapped("qty_at_subrent_wh"))
    available = owned + subrent_wh
    shortage = max(0.0, qty_needed - available)
    return {
        "owned_qty": owned,
        "subrent_wh_qty": subrent_wh,
        "available_qty": available,
        "shortage_qty": shortage,
        "lot_ids": lots.ids,
    }


def status_by_product(env, company_ids=None):
    Lot = env["rental.subrent.lot"]
    domain = [("state", "!=", "closed")]
    if company_ids:
        domain.append(("company_id", "in", list(company_ids)))
    lots = Lot.search(domain)
    by_product = defaultdict(lambda: {"at_wh": 0.0, "on_customer": 0.0, "lots": 0})
    for lot in lots:
        row = by_product[lot.product_id.id]
        row["at_wh"] += lot.qty_at_subrent_wh
        row["on_customer"] += lot.qty_on_customer
        row["lots"] += 1
        row["product"] = lot.product_id
    return by_product
