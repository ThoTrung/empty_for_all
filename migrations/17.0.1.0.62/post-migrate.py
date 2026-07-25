# -*- coding: utf-8 -*-
"""Re-stamp company_id on shared commercial partners (hotfix if 61 skipped)."""

import logging
from collections import defaultdict

_logger = logging.getLogger(__name__)


def _table_exists(cr, table):
    cr.execute("SELECT to_regclass(%s)", (table,))
    return bool(cr.fetchone()[0])


def _collect_partner_companies(cr):
    """partner_id -> set of company_ids from business documents."""
    inferred = defaultdict(set)
    queries = []

    if _table_exists(cr, "sale_order"):
        queries.append(
            """
            SELECT partner_id, company_id FROM sale_order
             WHERE partner_id IS NOT NULL AND company_id IS NOT NULL
            UNION ALL
            SELECT partner_invoice_id, company_id FROM sale_order
             WHERE partner_invoice_id IS NOT NULL AND company_id IS NOT NULL
            UNION ALL
            SELECT partner_shipping_id, company_id FROM sale_order
             WHERE partner_shipping_id IS NOT NULL AND company_id IS NOT NULL
            """
        )

    if _table_exists(cr, "purchase_order"):
        queries.append(
            """
            SELECT partner_id, company_id FROM purchase_order
             WHERE partner_id IS NOT NULL AND company_id IS NOT NULL
            """
        )

    if _table_exists(cr, "account_move"):
        queries.append(
            """
            SELECT partner_id, company_id FROM account_move
             WHERE partner_id IS NOT NULL AND company_id IS NOT NULL
            """
        )

    if _table_exists(cr, "rental_contract"):
        queries.append(
            """
            SELECT a_company_party, company_id FROM rental_contract
             WHERE a_company_party IS NOT NULL AND company_id IS NOT NULL
            UNION ALL
            SELECT a_party, company_id FROM rental_contract
             WHERE a_party IS NOT NULL AND company_id IS NOT NULL
            UNION ALL
            SELECT b_party, company_id FROM rental_contract
             WHERE b_party IS NOT NULL AND company_id IS NOT NULL
            """
        )

    for sql in queries:
        cr.execute(sql)
        for partner_id, company_id in cr.fetchall():
            if partner_id and company_id:
                inferred[partner_id].add(company_id)
    return inferred


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    Partner = env["res.partner"].with_context(active_test=False)

    inferred = _collect_partner_companies(cr)
    stamped = 0
    ambiguous = []

    # Priority: res.company.partner_id → that company (fixes Access Error on company form).
    cr.execute(
        """
        UPDATE res_partner p
           SET company_id = c.id
          FROM res_company c
         WHERE c.partner_id = p.id
           AND p.company_id IS NULL
        """
    )
    stamped = cr.rowcount or 0
    Partner.invalidate_model(["company_id"])

    shared = Partner.search([
        ("company_id", "=", False),
        ("partner_share", "=", True),
    ])

    for partner in shared:
        if partner.company_id:
            continue
        companies = inferred.get(partner.id, set())
        if partner.parent_id and partner.parent_id.company_id:
            companies = {partner.parent_id.company_id.id}
        if len(companies) == 1:
            company_id = next(iter(companies))
            partner.write({"company_id": company_id})
            stamped += 1
        elif len(companies) > 1:
            ambiguous.append((partner.id, partner.display_name, sorted(companies)))

    # Propagate parent company_id to remaining shared children (multi-pass).
    for _ in range(5):
        children = Partner.search([
            ("company_id", "=", False),
            ("partner_share", "=", True),
            ("parent_id.company_id", "!=", False),
        ])
        if not children:
            break
        for child in children:
            child.write({"company_id": child.parent_id.company_id.id})
            stamped += 1

    remaining = Partner.search_count([
        ("company_id", "=", False),
        ("partner_share", "=", True),
    ])
    _logger.info(
        "rental 17.0.1.0.62: stamped company_id on %s shared partners; "
        "%s ambiguous; %s shared commercial still without company_id",
        stamped,
        len(ambiguous),
        remaining,
    )
    for pid, name, companies in ambiguous[:50]:
        _logger.warning(
            "rental 17.0.1.0.62: partner %s (%s) linked to multiple companies %s — left shared",
            pid,
            name,
            companies,
        )
