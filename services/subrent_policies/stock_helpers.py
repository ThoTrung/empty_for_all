# -*- coding: utf-8 -*-
"""Shared stock helpers for subrent policies."""
from odoo import _, fields
from odoo.exceptions import UserError


def validate_picking(picking):
    picking = picking.sudo()
    picking.do_unreserve()
    for move in picking.move_ids.filtered(lambda m: m.state not in ("done", "cancel")):
        move.quantity = move.product_uom_qty
        move.picked = True
    result = picking.with_context(
        cancel_backorder=True,
        skip_backorder=True,
        skip_sanity_check=True,
        skip_sms=True,
    ).button_validate()
    if isinstance(result, dict):
        picking.with_context(cancel_backorder=True)._action_done()


def get_owned_stock_location(company):
    wh = company.env["stock.warehouse"].sudo().search(
        [("company_id", "=", company.id)], limit=1
    )
    if not wh or not wh.lot_stock_id:
        raise UserError(_("Công ty %(c)s chưa có kho tồn.") % {"c": company.display_name})
    return wh.lot_stock_id


def get_warehouse(company):
    wh = company.env["stock.warehouse"].sudo().search(
        [("company_id", "=", company.id)], limit=1
    )
    if not wh:
        raise UserError(_("Công ty %(c)s chưa có kho.") % {"c": company.display_name})
    return wh


def product_onhand_at_location(env, product, location, company):
    Quant = env["stock.quant"].sudo()
    groups = Quant.read_group(
        [
            ("product_id", "=", product.id),
            ("location_id", "child_of", location.id),
            ("company_id", "=", company.id),
        ],
        ["quantity:sum"],
        [],
    )
    return groups[0].get("quantity", 0.0) if groups else 0.0


def create_incoming_picking(receipt, dest_location):
    company = receipt.company_id
    src = company._rental_subrent_supplier_location()
    wh = get_warehouse(company)
    picking_type = wh.in_type_id
    if not picking_type:
        raise UserError(_("Không tìm thấy kiểu phiếu nhập kho."))
    picking = receipt.env["stock.picking"].sudo().with_company(company).create({
        "picking_type_id": picking_type.id,
        "location_id": src.id,
        "location_dest_id": dest_location.id,
        "company_id": company.id,
        "partner_id": receipt.supplier_id.id,
        "origin": receipt.name,
        "scheduled_date": fields.Datetime.to_datetime(receipt.date),
    })
    Move = receipt.env["stock.move"].sudo().with_company(company)
    for line in receipt.line_ids:
        Move.create({
            "name": line.product_id.display_name,
            "product_id": line.product_id.id,
            "product_uom_qty": line.qty,
            "product_uom": line.product_id.uom_id.id,
            "picking_id": picking.id,
            "location_id": src.id,
            "location_dest_id": dest_location.id,
            "company_id": company.id,
        })
    picking.action_confirm()
    return picking


def create_outgoing_picking(return_doc, lines, src_location):
    company = return_doc.company_id
    dest = company._rental_subrent_supplier_location()
    wh = get_warehouse(company)
    picking_type = wh.out_type_id
    if not picking_type:
        raise UserError(_("Không tìm thấy kiểu phiếu xuất kho."))
    picking = return_doc.env["stock.picking"].sudo().with_company(company).create({
        "picking_type_id": picking_type.id,
        "location_id": src_location.id,
        "location_dest_id": dest.id,
        "company_id": company.id,
        "partner_id": return_doc.supplier_id.id,
        "origin": return_doc.name,
        "scheduled_date": fields.Datetime.to_datetime(return_doc.date),
    })
    Move = return_doc.env["stock.move"].sudo().with_company(company)
    for line in lines:
        product = line.product_id
        Move.create({
            "name": product.display_name,
            "product_id": product.id,
            "product_uom_qty": line.qty,
            "product_uom": product.uom_id.id,
            "picking_id": picking.id,
            "location_id": src_location.id,
            "location_dest_id": dest.id,
            "company_id": company.id,
        })
    picking.action_confirm()
    return picking
