# -*- coding: utf-8 -*-
from odoo import SUPERUSER_ID, api


def post_init_hook(cr, registry):
    """Existing contracts with lots → tracked; others keep simple default."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    Contract = env["rental.subrent.contract"].sudo()
    for contract in Contract.search([]):
        if contract.lot_ids and contract.policy_code != "tracked":
            # bypass write lock via SQL-like: no qty yet conflict — use context
            contract.with_context(rental_subrent_force_policy=True).write(
                {"policy_code": "tracked"}
            )
