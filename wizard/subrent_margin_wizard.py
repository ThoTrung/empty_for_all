# -*- coding: utf-8 -*-
from odoo import _, api, fields, models

from odoo.addons.rental_subrent.services.rental_subrent_margin_services import (
    calc_subrent_margin,
)


class SubrentMarginWizard(models.TransientModel):
    _name = "rental.subrent.margin.wizard"
    _description = "Báo cáo margin thuê ngoài"

    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    date_from = fields.Date(required=True, default=fields.Date.context_today)
    date_to = fields.Date(required=True, default=fields.Date.context_today)
    line_ids = fields.One2many(
        "rental.subrent.margin.wizard.line",
        "wizard_id",
        string="Chi tiết",
    )
    amount_revenue = fields.Float(string="Tổng doanh thu", readonly=True)
    amount_cost = fields.Float(string="Tổng chi phí NCC", readonly=True)
    amount_margin = fields.Float(string="Margin", readonly=True)

    def action_compute(self):
        self.ensure_one()
        rows = calc_subrent_margin(
            self.env, self.date_from, self.date_to, company_ids=[self.company_id.id]
        )
        self.line_ids.unlink()
        Line = self.env["rental.subrent.margin.wizard.line"]
        total_r = total_c = 0.0
        for row in rows:
            Line.create({
                "wizard_id": self.id,
                "lot_id": row["lot_id"],
                "product_id": row["product_id"],
                "supplier_id": row["supplier_id"],
                "cost_days": row["cost_days"],
                "amount_cost": row["cost"],
                "amount_revenue": row["revenue"],
                "amount_margin": row["margin"],
            })
            total_r += row["revenue"]
            total_c += row["cost"]
        self.write({
            "amount_revenue": total_r,
            "amount_cost": total_c,
            "amount_margin": total_r - total_c,
        })
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }


class SubrentMarginWizardLine(models.TransientModel):
    _name = "rental.subrent.margin.wizard.line"
    _description = "Dòng margin thuê ngoài"

    wizard_id = fields.Many2one("rental.subrent.margin.wizard", ondelete="cascade")
    lot_id = fields.Many2one("rental.subrent.lot", string="Lô")
    product_id = fields.Many2one("product.product", string="Sản phẩm")
    supplier_id = fields.Many2one("res.partner", string="NCC")
    cost_days = fields.Integer(string="Ngày tính cost")
    amount_cost = fields.Float(string="Chi phí")
    amount_revenue = fields.Float(string="Doanh thu")
    amount_margin = fields.Float(string="Margin")
