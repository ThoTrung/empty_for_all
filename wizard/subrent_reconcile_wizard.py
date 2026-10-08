# -*- coding: utf-8 -*-
from odoo import _, fields, models

from odoo.addons.rental_subrent.services.rental_subrent_reconcile_services import (
    reconcile_subrent_stock,
)


class SubrentReconcileWizard(models.TransientModel):
    _name = "rental.subrent.reconcile.wizard"
    _description = "Đối soát kho thuê ngoài vs sổ lô"

    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    line_ids = fields.One2many(
        "rental.subrent.reconcile.wizard.line",
        "wizard_id",
        string="Lệch",
    )
    note = fields.Text(readonly=True)

    def action_compute(self):
        self.ensure_one()
        diffs = reconcile_subrent_stock(self.env, self.company_id)
        self.line_ids.unlink()
        Line = self.env["rental.subrent.reconcile.wizard.line"]
        for d in diffs:
            Line.create({
                "wizard_id": self.id,
                "product_id": d["product_id"],
                "quant_qty": d["quant_qty"],
                "ledger_qty": d["ledger_qty"],
                "difference": d["difference"],
            })
        self.note = (
            _("Không lệch.") if not diffs else _("Có %(n)s sản phẩm lệch.") % {"n": len(diffs)}
        )
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }


class SubrentReconcileWizardLine(models.TransientModel):
    _name = "rental.subrent.reconcile.wizard.line"
    _description = "Dòng đối soát thuê ngoài"

    wizard_id = fields.Many2one("rental.subrent.reconcile.wizard", ondelete="cascade")
    product_id = fields.Many2one("product.product", string="Sản phẩm")
    quant_qty = fields.Float(string="Tồn WH/Subrent")
    ledger_qty = fields.Float(string="Theo sổ lô")
    difference = fields.Float(string="Lệch (kho − sổ)")
