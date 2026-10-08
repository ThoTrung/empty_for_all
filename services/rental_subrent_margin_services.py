# -*- coding: utf-8 -*-
"""Margin: revenue (customer on-hire days) vs cost (NCC possession calendar days)."""
from datetime import timedelta

from odoo import fields

from odoo.addons.rental.services.rental_contract_services import (
    rental_days_between_with_holiday,
    unit_price_for_transport_line,
)


def _overlap_days(a0, a1, b0, b1):
    start = max(a0, b0)
    end = min(a1, b1)
    if end < start:
        return 0
    return (end - start).days + 1


def _contract_ratio(contract, product):
    tmpl = product.product_tmpl_id
    line = contract.rental_contract_line_ids.filtered(
        lambda l: l.product_tmpl_id == tmpl
    )[:1]
    list_price = tmpl.list_price or 0.0
    if not line or not list_price:
        return 1.0
    return (line.price_unit or 0.0) / list_price


def calc_subrent_margin(env, date_from, date_to, company_ids=None):
    """Return list of dict rows: lot, revenue, cost, margin."""
    date_from = fields.Date.to_date(date_from)
    date_to = fields.Date.to_date(date_to)
    Lot = env["rental.subrent.lot"]
    domain = []
    if company_ids:
        domain.append(("company_id", "in", list(company_ids)))
    lots = Lot.search(domain)
    rows = []
    for lot in lots:
        if not lot.date_start:
            continue
        poss_start = lot.date_start
        poss_end = lot.date_end or date_to
        cost_days = _overlap_days(poss_start, poss_end, date_from, date_to)
        min_months = lot.minimum_rental_months or 0.0
        if min_months and lot.date_end and lot.date_end <= date_to:
            min_days = int(min_months * 30)
            cost_days = max(
                cost_days,
                _overlap_days(
                    poss_start,
                    poss_start + timedelta(days=min_days - 1),
                    date_from,
                    date_to,
                ),
            )
        cost_per_day = (lot.cost_unit or 0.0) / 30.0
        open_qty = max((lot.qty_received or 0.0) - (lot.qty_damaged or 0.0), 0.0)
        cost = cost_days * cost_per_day * open_qty

        revenue = 0.0
        delivers = lot.ledger_ids.filtered(lambda l: l.move_type == "deliver_customer")
        for led in delivers:
            tline = led.transport_line_id
            if not tline or not led.date:
                continue
            end = lot.date_end or date_to
            later = lot.ledger_ids.filtered(
                lambda l, d=led.date, i=led.id: l.date
                and l.date >= d
                and l.move_type in ("return_customer", "damage")
                and l.id > i
            ).sorted(lambda l: (l.date, l.id))
            if later:
                end = min(end, later[0].date)
            contract = tline.rental_contract_id
            if not contract:
                continue
            seg_start = max(led.date, date_from)
            seg_end = min(end, date_to)
            if seg_end < seg_start:
                continue
            include = bool(getattr(contract, "include_start_day_current", False))
            days = rental_days_between_with_holiday(
                env, contract, seg_start, seg_end, include_start_day=include
            )
            ratio = _contract_ratio(contract, tline.product_id)
            unit = unit_price_for_transport_line(
                contract, tline.product_id, ratio, seg_end
            )
            revenue += days * unit * led.qty

        rows.append({
            "lot": lot,
            "lot_id": lot.id,
            "product_id": lot.product_id.id,
            "supplier_id": lot.supplier_id.id,
            "subrent_contract_id": lot.subrent_contract_id.id,
            "cost_days": cost_days,
            "cost": cost,
            "revenue": revenue,
            "margin": revenue - cost,
        })
    return rows
