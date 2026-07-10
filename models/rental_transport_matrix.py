# -*- coding: utf-8 -*-

import html
from collections import OrderedDict

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


def _variant_price_multiplier(product):
    """Combined Price Multiplier (product of PTAV price_multiplier values)."""
    mult = 1.0
    for v in product.product_template_attribute_value_ids:
        m = v.price_multiplier or 1.0
        mult *= m if m > 0 else 1.0
    return mult


def _linear_meter_factor_for_product(product):
    """Meters factor for Tổng MD: Price Multiplier when UOM is linear meter."""
    if not product.uom_id.is_linear_meter_variant:
        return None
    mult = _variant_price_multiplier(product)
    return mult if mult > 0 else None


def _variant_sort_key_from_info(info):
    """Sort key: Price Multiplier ascending, then label."""
    if not isinstance(info, dict):
        return (1, 0.0, "")
    label = (info.get("variant_name") or info.get("prod_name") or info.get("name") or "").strip()
    mult = info.get("price_multiplier")
    if mult is not None and mult > 0:
        return (0, mult, label.casefold())
    return (1, 0.0, label.casefold())


def _sort_products_odict(products_odict):
    items = sorted(products_odict.items(), key=lambda kv: _variant_sort_key_from_info(kv[1]))
    return OrderedDict(items)


def _format_md_value(value):
    if value is None or value == 0:
        return ""
    if abs(value - round(value)) < 1e-9:
        return str(int(round(value)))
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _sum_linear_meters(cell_qty_by_prod, prod_ids, lengths_by_prod):
    total = 0.0
    for pid in prod_ids:
        length = lengths_by_prod.get(pid)
        if length is None:
            continue
        qty = cell_qty_by_prod.get(pid, 0) or 0
        total += qty * length
    return total


def _group_needs_md_column(env, prods, prod_order):
    """True when the template group should show a Tổng MD column."""
    if not prod_order:
        return False
    product = env["product.product"].browse(prod_order[0])
    if not product.exists():
        return False
    return bool(product.uom_id.is_linear_meter_variant)


class RentalTransportMatrix(models.Model):
    """
    Persisted "confirmation table for rental volume" for a contract + date range.
    Users generate it from the contract, review the matrix, then download Excel.
    """

    _name = "rental.transport.matrix"
    _description = "Rental Transport Matrix"
    _rec_name = "name"
    _order = "id desc"

    name = fields.Char(string="Name", required=True, default=lambda self: _("Rental Volume Confirmation"))

    rental_contract_id = fields.Many2one(
        "rental.contract",
        string="Rental Contract",
        required=True,
        index=True,
        ondelete="cascade",
    )
    company_id = fields.Many2one(related="rental_contract_id.company_id", store=True, readonly=True, index=True)
    currency_id = fields.Many2one(related="rental_contract_id.currency_id", store=True, readonly=True)

    # Party A (tenant) / Party B (lessor) — for display on form
    a_company_name = fields.Char(related="rental_contract_id.a_company_party.name", readonly=True)
    a_representative_name = fields.Char(related="rental_contract_id.a_name", readonly=True)
    a_representative_function = fields.Char(related="rental_contract_id.a_function", readonly=True)
    b_company_name = fields.Char(related="rental_contract_id.b_company_party.name", readonly=True)
    b_representative_name = fields.Char(related="rental_contract_id.b_name", readonly=True)
    b_representative_function = fields.Char(related="rental_contract_id.b_function", readonly=True)

    start_date = fields.Date(string="Start date", required=True)
    end_date = fields.Date(string="End date", required=True)

    product_ids = fields.Many2many(
        "product.product",
        string="Products (variants)",
        compute="_compute_matrix",
        store=True,
        readonly=True,
    )

    matrix_html = fields.Html(
        string="Confirmation table for rental volume",
        compute="_compute_matrix",
        sanitize=False,
    )

    @api.constrains("start_date", "end_date")
    def _check_date_range(self):
        for rec in self:
            if rec.start_date and rec.end_date and rec.end_date < rec.start_date:
                raise models.ValidationError(_("End date must be on or after Start date."))

    @api.constrains("rental_contract_id", "start_date", "end_date")
    def _check_no_overlap_same_contract(self):
        """Inclusive date ranges on the same contract must not overlap."""
        for rec in self:
            if not rec.rental_contract_id or not rec.start_date or not rec.end_date:
                continue
            other = self.search(
                [
                    ("rental_contract_id", "=", rec.rental_contract_id.id),
                    ("id", "!=", rec.id),
                    ("start_date", "<=", rec.end_date),
                    ("end_date", ">=", rec.start_date),
                ],
                limit=1,
            )
            if other:
                raise ValidationError(
                    _(
                        "The date range overlaps another confirmation table on this contract: %(name)s.",
                        name=other.display_name,
                    )
                )

    @api.depends("rental_contract_id", "start_date", "end_date")
    def _compute_matrix(self):
        """
        Build an HTML table similar to the Excel:
        - First header row: product templates (merged for variants)
        - Second header row: variant names (or product name if single variant)
        - Optional opening row: tổng hợp các transport có ngày < start_date (Tồn đầu kỳ)
        - Data rows: transports in [start_date, end_date]
        - Summary row: Tổng KL Cuối T{MM.YYYY}
        """
        Transport = self.env["rr.transport"]
        for rec in self:
            rec.product_ids = [(6, 0, [])]
            rec.matrix_html = ""
            if not rec.rental_contract_id or not rec.start_date or not rec.end_date:
                continue

            # Transports trong kỳ [start_date, end_date]
            transports_in_range = Transport.search(
                [
                    ("rental_contract_id", "=", rec.rental_contract_id.id),
                    ("start_rental_or_return_date", ">=", rec.start_date),
                    ("start_rental_or_return_date", "<=", rec.end_date),
                ],
                order="start_rental_or_return_date asc, id asc",
            )
            # Transports trước start_date → tổng hợp 1 dòng đầu kỳ
            transports_before = Transport.search(
                [
                    ("rental_contract_id", "=", rec.rental_contract_id.id),
                    ("start_rental_or_return_date", "<", rec.start_date),
                ],
            )

            # Build product_tmpls + columns from both before and in-range (để cột đủ hết sản phẩm)
            product_tmpls = OrderedDict()
            variant_product_ids = []
            for transport in transports_before | transports_in_range:
                for line in transport.transport_line_ids:
                    tmpl = line.product_tmpl_id
                    prod = line.product_id
                    if not tmpl or not prod:
                        continue
                    if tmpl.id not in product_tmpls:
                        product_tmpls[tmpl.id] = {
                            "tmpl_name": tmpl.display_name,
                            "products": OrderedDict(),
                        }
                    if prod.id not in product_tmpls[tmpl.id]["products"]:
                        product_tmpls[tmpl.id]["products"][prod.id] = {
                            "prod_name": prod.display_name,
                            "variant_name": prod.product_template_variant_value_ids.name,
                            "price_multiplier": _variant_price_multiplier(prod),
                        }
                        variant_product_ids.append(prod.id)

            for _tmpl_id, tmpl_info in product_tmpls.items():
                tmpl_info["products"] = _sort_products_odict(tmpl_info["products"])

            rec.product_ids = [(6, 0, variant_product_ids)]

            groups_meta = []
            for tmpl_id, tmpl_info in product_tmpls.items():
                prods = tmpl_info["products"]
                prod_order = list(prods.keys())
                lengths = {
                    pid: _linear_meter_factor_for_product(
                        rec.env["product.product"].browse(pid)
                    )
                    for pid in prod_order
                }
                needs_md = _group_needs_md_column(rec.env, prods, prod_order)
                groups_meta.append({
                    "tmpl_id": tmpl_id,
                    "tmpl_name": tmpl_info["tmpl_name"],
                    "products": prods,
                    "prod_order": prod_order,
                    "lengths": lengths,
                    "needs_md": needs_md,
                })

            def _cells_from_transports(transport_set):
                cell_qty = {}
                for transport in transport_set:
                    for line in transport.transport_line_ids:
                        if not line.product_id:
                            continue
                        cell_qty[line.product_id.id] = cell_qty.get(line.product_id.id, 0) + (line.qty or 0)
                return cell_qty

            # Dòng đầu kỳ: tổng hợp transport < start_date
            opening_cells = _cells_from_transports(transports_before)
            has_opening = any(v != 0 for v in opening_cells.values())

            # Data rows: từng transport trong kỳ
            rows = []
            for transport in transports_in_range:
                d = transport.start_rental_or_return_date
                date_str = d.strftime("%-d/%-m/%Y") if d else ""
                plate = transport.plate or ""
                cell_qty = _cells_from_transports(transport)
                rows.append({"date": date_str, "plate": plate, "cells": cell_qty})

            # Tổng cột cho dòng "Tổng KL Cuối T..." = Tồn đầu kỳ + tổng các dòng trong kỳ
            total_cells = dict(opening_cells)
            for r in rows:
                for prod_id, qty in r["cells"].items():
                    total_cells[prod_id] = total_cells.get(prod_id, 0) + qty

            if not product_tmpls and not rows and not has_opening:
                rec.matrix_html = "<div class='text-muted'>No transports for this contract in or before the selected date range.</div>"
                continue

            def esc(x):
                return html.escape(str(x) if x is not None else "")

            def _append_group_qty_md_cells(tds, cell_qty, td_qty_class, td_md_class):
                """Append qty (+ optional Tổng MD) cells for each template group."""
                for g in groups_meta:
                    if g["needs_md"]:
                        for pid in g["prod_order"]:
                            val = cell_qty.get(pid, 0) or ""
                            tds.append(
                                f"<td class='text-end rental-matrix-col-qty {td_qty_class}'>{esc(val)}</td>"
                            )
                        md = _sum_linear_meters(cell_qty, g["prod_order"], g["lengths"])
                        tds.append(
                            f"<td class='text-end rental-matrix-col-md {td_md_class}'>{esc(_format_md_value(md))}</td>"
                        )
                    else:
                        pid = g["prod_order"][0]
                        val = cell_qty.get(pid, 0) or ""
                        tds.append(
                            f"<td class='text-end rental-matrix-col-qty {td_qty_class}'>{esc(val)}</td>"
                        )

            head1 = [
                "<th rowspan='2' class='rental-matrix-col-stt'>STT</th>",
                "<th rowspan='2' class='rental-matrix-col-date'>Ngày tháng</th>",
                "<th rowspan='2' class='rental-matrix-col-plate'>BKS Xe</th>",
            ]
            head2 = []
            for g in groups_meta:
                n = len(g["prod_order"])
                if g["needs_md"]:
                    head1.append(
                        f"<th colspan='{n + 1}' class='text-center rental-matrix-col-product'>"
                        f"{esc(g['tmpl_name'])}</th>"
                    )
                    for pid in g["prod_order"]:
                        pinfo = g["products"][pid]
                        sub = pinfo["variant_name"] or pinfo["prod_name"]
                        head2.append(
                            f"<th class='text-center rental-matrix-col-qty rental-matrix-th-wrap'>{esc(sub)}</th>"
                        )
                    head2.append(
                        "<th class='text-center rental-matrix-col-md rental-matrix-th-wrap'>Tổng MD</th>"
                    )
                else:
                    pinfo = g["products"][g["prod_order"][0]]
                    label = pinfo["prod_name"]
                    head1.append(
                        f"<th rowspan='2' class='text-center rental-matrix-col-product rental-matrix-th-wrap'>"
                        f"{esc(label)}</th>"
                    )
            need_second_row = any(g["needs_md"] for g in groups_meta)

            body_rows = []
            row_index = 0

            # 1) Dòng tồn đầu kỳ (transport < start_date)
            if has_opening:
                row_index += 1
                tds = [
                    f"<td class='text-center rental-matrix-col-stt'>{esc(row_index)}</td>",
                    "<td class='rental-matrix-col-date rental-matrix-row-opening fw-bold' colspan='2'>Tồn đầu kỳ</td>",
                ]
                _append_group_qty_md_cells(tds, opening_cells, "rental-matrix-row-opening", "rental-matrix-row-opening")
                body_rows.append("<tr>" + "".join(tds) + "</tr>")

            # 2) Các dòng transport trong kỳ
            for r in rows:
                row_index += 1
                tds = [
                    f"<td class='text-center rental-matrix-col-stt'>{esc(row_index)}</td>",
                    f"<td class='rental-matrix-col-date'>{esc(r['date'])}</td>",
                    f"<td class='rental-matrix-col-plate'>{esc(r['plate'])}</td>",
                ]
                _append_group_qty_md_cells(tds, r["cells"], "", "")
                body_rows.append("<tr>" + "".join(tds) + "</tr>")

            # 3) Dòng tổng cuối: Tổng KL Cuối T{MM.YYYY}
            total_label = f"Tổng KL Cuối T{rec.end_date.strftime('%m.%Y')}"
            tds = [
                "<td class='text-center rental-matrix-col-stt'></td>",
                f"<td class='rental-matrix-col-date rental-matrix-row-total' colspan='2'>{esc(total_label)}</td>",
            ]
            _append_group_qty_md_cells(tds, total_cells, "rental-matrix-row-total fw-bold", "rental-matrix-row-total fw-bold")
            body_rows.append("<tr>" + "".join(tds) + "</tr>")

            css = """
<style>
.rental-matrix-wrap { overflow-x: auto; overflow-y: visible; }
.rental-matrix { border-collapse: collapse; table-layout: auto; width: max-content; min-width: 100%; }
.rental-matrix th, .rental-matrix td { border: 1px solid #ddd; padding: 4px 6px; vertical-align: middle; }
.rental-matrix thead th { background: #f6f6f6; font-weight: 600; }
.rental-matrix-col-stt { width: 2.5em; min-width: 2.5em; }
.rental-matrix-col-date { width: 5.5em; min-width: 5em; }
.rental-matrix-col-plate { width: 7em; min-width: 6em; }
.rental-matrix-col-qty { min-width: 3.5em; white-space: nowrap; }
.rental-matrix-col-md { min-width: 4em; background: #e8f5e9; white-space: nowrap; font-weight: bold; }
.rental-matrix th.rental-matrix-th-wrap,
.rental-matrix th.rental-matrix-col-product {
    white-space: normal !important;
    word-break: break-word;
    overflow-wrap: anywhere;
    line-height: 1.25;
    hyphens: auto;
    min-width: 3.5em;
    max-width: 8em;
}
.rental-matrix th.rental-matrix-col-product { line-height: 1.2; }
.rental-matrix-row-total { background: #f0f0f0; font-weight: 600; }
.rental-matrix-row-opening { background: #fafafa; }
.text-end { text-align: right; }
.text-center { text-align: center; }
.fw-bold { font-weight: bold; }
</style>
"""

            thead = "<thead><tr>{}</tr>".format("".join(head1))
            if need_second_row:
                thead += "<tr>{}</tr>".format("".join(head2))
            thead += "</thead>"

            rec.matrix_html = (
                css
                + "<div class='rental-matrix-wrap'>"
                + "<table class='rental-matrix'>"
                + thead
                + "<tbody>{}</tbody>".format("".join(body_rows) if body_rows else "<tr><td colspan='999'>No data</td></tr>")
                + "</table></div>"
            )

    def action_download_excel(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": f"/rental/transport-matrix/{self.id}/download",
            "target": "new",
        }

    def action_recalculate_matrix(self):
        """Rebuild matrix_html from current transports (same date range)."""
        self._compute_matrix()
        return True

