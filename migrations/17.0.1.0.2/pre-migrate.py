# -*- coding: utf-8 -*-
# Điền người giao/nhận từ hợp đồng trước khi cột chuyển sang NOT NULL.


def migrate(cr, version):
    from odoo.tools import sql

    if not sql.table_exists(cr, "rr_transport") or not sql.table_exists(cr, "rental_contract"):
        return

    cr.execute(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'rental_contract'
          AND column_name IN ('a_party_id', 'a_party', 'b_party_id', 'b_party')
        """
    )
    cols = {row[0] for row in cr.fetchall()}
    if "a_party_id" in cols and "b_party_id" in cols:
        a_col, b_col = "a_party_id", "b_party_id"
    elif "a_party" in cols and "b_party" in cols:
        a_col, b_col = "a_party", "b_party"
    else:
        return

    cr.execute(
        f"""
        UPDATE rr_transport AS t
        SET
            deliverer_partner_id = COALESCE(
                t.deliverer_partner_id,
                CASE WHEN t.type = 'return' THEN c.{a_col} ELSE c.{b_col} END
            ),
            receiver_partner_id = COALESCE(
                t.receiver_partner_id,
                CASE WHEN t.type = 'return' THEN c.{b_col} ELSE c.{a_col} END
            )
        FROM rental_contract AS c
        WHERE t.rental_contract_id = c.id
          AND (t.deliverer_partner_id IS NULL OR t.receiver_partner_id IS NULL)
        """
    )
