# -*- coding: utf-8 -*-

import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    @api.model
    def _spa_mark_settlement_recompute(self, moves):
        res = super()._spa_mark_settlement_recompute(moves)
        if moves:
            # Narrow flush (never a whole-environment flush):
            # _spa_notify_late_refund_on_locked_payslips
            # below reads spa_settled_date/spa_is_settled (sale.order) and
            # spa_fully_paid_date (account.move) via search(), which only sees
            # what's actually written to the DB — but this hook runs from
            # AccountPartialReconcile.create(), a hot path (bulk bank-statement
            # reconcile), so flushing the WHOLE environment on every call would
            # be a needless "flush storm". Flush just the two models the notify
            # query depends on.
            self.env["sale.order"].flush_model(["spa_is_settled", "spa_settled_date"])
            self.env["account.move"].flush_model(["spa_fully_paid_date"])
            try:
                # A SQL-level error inside would otherwise abort the whole DB
                # transaction (not just this Python call) — use a savepoint so
                # a bug in this best-effort notification can never roll back
                # the accounting reconcile/payment transaction that triggered it.
                with self.env.cr.savepoint():
                    self.env["spa.staff.payroll"]._spa_notify_late_refund_on_locked_payslips(moves)
            except Exception:
                _logger.exception(
                    "spa_staff_payroll: _spa_notify_late_refund_on_locked_payslips failed "
                    "for moves %s — reconcile/payment still committed.",
                    moves.ids,
                )
        return res
