# -*- coding: utf-8 -*-
# Chạy trước khi ORM cập nhật schema (xóa cột picking_id trên rr_transport).


def migrate(cr, version):
    from odoo.tools import sql

    if not sql.table_exists(cr, "rr_transport"):
        return
    cr.execute(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'rr_transport' AND column_name = 'picking_id'
        """
    )
    if not cr.fetchone():
        return
    if not sql.column_exists(cr, "stock_picking", "rental_transport_id"):
        sql.create_column(cr, "stock_picking", "rental_transport_id", "int4")
    cr.execute(
        """
        UPDATE stock_picking AS sp
        SET rental_transport_id = rt.id
        FROM rr_transport AS rt
        WHERE rt.picking_id = sp.id
        """
    )
    cr.execute(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'rr_transport' AND column_name = 'reversal_picking_id'
        """
    )
    if cr.fetchone():
        cr.execute(
            """
            UPDATE stock_picking AS sp
            SET rental_transport_id = rt.id
            FROM rr_transport AS rt
            WHERE rt.reversal_picking_id = sp.id
              AND sp.rental_transport_id IS NULL
            """
        )
    cr.execute(
        """
        UPDATE rr_transport
        SET name = code
        WHERE code IS NOT NULL AND (name IS NULL OR name = '')
        """
    )
