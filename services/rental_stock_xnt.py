# -*- coding: utf-8 -*-
"""Warehouse stock on-hand and Xuất–Nhập–Tồn from done stock.move.

Independent of rental LIFO / rr.transport (DEC-17 on-hire). Includes every
done move that touches internal locations: rental pickings, SO, PO, adjustments.
"""
from collections import defaultdict
from datetime import datetime, time, timedelta

from odoo import fields


def get_internal_location_ids(env, company_ids, warehouse_ids=None):
    """Internal stock locations for companies, optionally scoped to warehouses."""
    Location = env["stock.location"].sudo()
    Warehouse = env["stock.warehouse"].sudo()
    company_ids = list(company_ids or env.companies.ids)
    if not company_ids:
        return []

    wh_domain = [("company_id", "in", company_ids)]
    if warehouse_ids:
        wh_domain.append(("id", "in", list(warehouse_ids)))
    warehouses = Warehouse.search(wh_domain)
    if not warehouses:
        return Location.search([
            ("usage", "=", "internal"),
            "|",
            ("company_id", "in", company_ids),
            ("company_id", "=", False),
        ]).ids

    location_ids = set()
    for warehouse in warehouses:
        if not warehouse.view_location_id:
            continue
        locs = Location.search([
            ("id", "child_of", warehouse.view_location_id.id),
            ("usage", "=", "internal"),
        ])
        location_ids.update(locs.ids)
    return list(location_ids)


def _day_start(day):
    day = fields.Date.to_date(day)
    return datetime.combine(day, time.min)


def _day_end_exclusive(day):
    day = fields.Date.to_date(day)
    return datetime.combine(day + timedelta(days=1), time.min)


def _product_domain(product_ids=None):
    domain = [("product_id.type", "=", "product")]
    if product_ids:
        domain.append(("product_id", "in", list(product_ids)))
    return domain


def _sum_moves_by_product(env, domain):
    """Return {product_id: qty_in_product_uom} for done moves matching domain."""
    Move = env["stock.move"].sudo()
    groups = Move.read_group(
        domain,
        ["product_id", "product_qty:sum"],
        ["product_id"],
        lazy=False,
    )
    result = {}
    for group in groups:
        product = group.get("product_id")
        if not product:
            continue
        result[product[0]] = group.get("product_qty") or 0.0
    return result


def _net_on_hand_before(env, location_ids, before_dt, product_ids=None):
    """Net qty in location set for moves with date < before_dt."""
    if not location_ids:
        return {}
    base = _product_domain(product_ids) + [
        ("state", "=", "done"),
        ("date", "<", before_dt),
    ]
    inbound = _sum_moves_by_product(
        env,
        base + [
            ("location_dest_id", "in", location_ids),
            ("location_id", "not in", location_ids),
        ],
    )
    outbound = _sum_moves_by_product(
        env,
        base + [
            ("location_id", "in", location_ids),
            ("location_dest_id", "not in", location_ids),
        ],
    )
    product_ids_seen = set(inbound) | set(outbound)
    return {
        pid: inbound.get(pid, 0.0) - outbound.get(pid, 0.0)
        for pid in product_ids_seen
    }


def _period_in_out(env, location_ids, start_dt, end_exclusive_dt, product_ids=None):
    if not location_ids:
        return {}, {}
    base = _product_domain(product_ids) + [
        ("state", "=", "done"),
        ("date", ">=", start_dt),
        ("date", "<", end_exclusive_dt),
    ]
    inbound = _sum_moves_by_product(
        env,
        base + [
            ("location_dest_id", "in", location_ids),
            ("location_id", "not in", location_ids),
        ],
    )
    outbound = _sum_moves_by_product(
        env,
        base + [
            ("location_id", "in", location_ids),
            ("location_dest_id", "not in", location_ids),
        ],
    )
    return inbound, outbound


def _lines_from_qty_map(env, qty_by_product, *, company_id=None, extra_vals=None):
    """Build sorted line dicts from {product_id: qty}, skipping zero qty."""
    extra = dict(extra_vals or {})
    Product = env["product.product"].sudo().browse(list(qty_by_product))
    products = {p.id: p for p in Product.exists()}
    lines = []
    for product_id, qty in qty_by_product.items():
        product = products.get(product_id)
        if not product or product.type != "product":
            continue
        if not qty:
            continue
        uom = product.uom_id
        row = {
            "company_id": company_id,
            "product_id": product.id,
            "product_tmpl_id": product.product_tmpl_id.id,
            "uom_id": uom.id if uom else False,
            "uom_name": uom.display_name if uom else "",
            "qty_on_hand": qty,
        }
        row.update(extra)
        lines.append(row)
    lines.sort(
        key=lambda r: (
            -abs(r.get("qty_on_hand") or 0.0),
            products[r["product_id"]].display_name,
        )
    )
    return lines


def calc_stock_on_hand_as_of(
    env,
    as_of_date,
    *,
    company_ids=None,
    warehouse_ids=None,
    product_ids=None,
):
    """Return on-hand lines in internal locations at end of ``as_of_date``."""
    as_of_date = fields.Date.to_date(as_of_date)
    company_ids = list(company_ids or env.companies.ids)
    end_exclusive = _day_end_exclusive(as_of_date)
    lines = []
    for company_id in company_ids:
        location_ids = get_internal_location_ids(env, [company_id], warehouse_ids)
        qty_map = _net_on_hand_before(env, location_ids, end_exclusive, product_ids)
        lines.extend(
            _lines_from_qty_map(
                env,
                qty_map,
                company_id=company_id,
                extra_vals={"as_of_date": as_of_date},
            )
        )
    lines.sort(
        key=lambda r: (-abs(r.get("qty_on_hand") or 0.0), r["product_id"])
    )
    return lines


def calc_xnt_lines(
    env,
    date_from,
    date_to,
    *,
    company_ids=None,
    warehouse_ids=None,
    product_ids=None,
):
    """Return XNT lines: opening, in, out, closing for the inclusive period."""
    date_from = fields.Date.to_date(date_from)
    date_to = fields.Date.to_date(date_to)
    company_ids = list(company_ids or env.companies.ids)
    start_dt = _day_start(date_from)
    end_exclusive = _day_end_exclusive(date_to)

    lines = []
    for company_id in company_ids:
        location_ids = get_internal_location_ids(env, [company_id], warehouse_ids)
        opening = _net_on_hand_before(env, location_ids, start_dt, product_ids)
        inbound, outbound = _period_in_out(
            env, location_ids, start_dt, end_exclusive, product_ids
        )
        product_ids_seen = set(opening) | set(inbound) | set(outbound)
        if product_ids:
            product_ids_seen &= set(product_ids)

        Product = env["product.product"].sudo().browse(list(product_ids_seen))
        products = {p.id: p for p in Product.exists()}
        for product_id in product_ids_seen:
            product = products.get(product_id)
            if not product or product.type != "product":
                continue
            open_qty = opening.get(product_id, 0.0)
            in_qty = inbound.get(product_id, 0.0)
            out_qty = outbound.get(product_id, 0.0)
            closing = open_qty + in_qty - out_qty
            if not any((open_qty, in_qty, out_qty, closing)):
                continue
            uom = product.uom_id
            lines.append({
                "company_id": company_id,
                "date_from": date_from,
                "date_to": date_to,
                "product_id": product.id,
                "product_tmpl_id": product.product_tmpl_id.id,
                "uom_id": uom.id if uom else False,
                "uom_name": uom.display_name if uom else "",
                "opening_qty": open_qty,
                "in_qty": in_qty,
                "out_qty": out_qty,
                "closing_qty": closing,
            })
    lines.sort(
        key=lambda r: (
            -(abs(r["closing_qty"]) + abs(r["in_qty"]) + abs(r["out_qty"])),
            r["product_id"],
        )
    )
    return lines


def summarize_xnt_for_dashboard(env, date_from, date_to, **kwargs):
    """Aggregate XNT for dashboard KPI + grouped bar (top products by movement)."""
    lines = calc_xnt_lines(env, date_from, date_to, **kwargs)
    by_uom = defaultdict(lambda: {
        "uom_id": False,
        "uom_name": "",
        "in_qty": 0.0,
        "out_qty": 0.0,
        "opening_qty": 0.0,
        "closing_qty": 0.0,
    })
    for line in lines:
        key = line["uom_id"] or 0
        bucket = by_uom[key]
        bucket["uom_id"] = line["uom_id"]
        bucket["uom_name"] = line["uom_name"] or ""
        bucket["in_qty"] += line["in_qty"]
        bucket["out_qty"] += line["out_qty"]
        bucket["opening_qty"] += line["opening_qty"]
        bucket["closing_qty"] += line["closing_qty"]

    ranked = sorted(
        lines,
        key=lambda r: (-(r["in_qty"] + r["out_qty"]), r["product_id"]),
    )[:12]
    Product = env["product.product"].browse([r["product_id"] for r in ranked])
    name_by_id = {p.id: p.display_name for p in Product}

    return {
        "lines": lines,
        "totals_by_uom": sorted(
            by_uom.values(),
            key=lambda r: (-(r["in_qty"] + r["out_qty"]), r["uom_name"]),
        ),
        "chart": {
            "labels": [
                "%s (%s)" % (name_by_id.get(r["product_id"], "?"), r["uom_name"] or "")
                for r in ranked
            ],
            "in_values": [r["in_qty"] for r in ranked],
            "out_values": [r["out_qty"] for r in ranked],
            "dataset_in_label": "Nhập",
            "dataset_out_label": "Xuất",
        },
    }
