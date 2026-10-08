# -*- coding: utf-8 -*-
from odoo import fields, models

from odoo.addons.rental_subrent.services.subrent_policies import get_policy


class SubrentPayableWizard(models.TransientModel):
    _name = "rental.subrent.payable.wizard"
    _description = "Công nợ thuê NCC (theo policy)"

    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    date_from = fields.Date(required=True, default=fields.Date.context_today)
    date_to = fields.Date(required=True, default=fields.Date.context_today)
    subrent_contract_id = fields.Many2one(
        "rental.subrent.contract",
        string="HĐ thuê ngoài",
        domain="[('company_id', '=', company_id), ('state', 'in', ('active', 'done'))]",
    )
    line_ids = fields.One2many(
        "rental.subrent.payable.wizard.line",
        "wizard_id",
        string="Chi tiết",
    )
    amount_total = fields.Float(string="Tổng", readonly=True)

    def action_compute(self):
        self.ensure_one()
        domain = [
            ("company_id", "=", self.company_id.id),
            ("state", "in", ("active", "done")),
        ]
        if self.subrent_contract_id:
            domain.append(("id", "=", self.subrent_contract_id.id))
        contracts = self.env["rental.subrent.contract"].search(domain)
        self.line_ids.unlink()
        Line = self.env["rental.subrent.payable.wizard.line"]
        total = 0.0
        for contract in contracts:
            policy = get_policy(contract.policy_code or "simple")
            rows = policy.compute_monthly_payable(contract, self.date_from, self.date_to)
            for row in rows:
                Line.create({
                    "wizard_id": self.id,
                    "subrent_contract_id": contract.id,
                    "product_tmpl_id": row.get("product_tmpl_id"),
                    "qty_open": row.get("qty_open", 0.0),
                    "cost_unit": row.get("cost_unit", 0.0),
                    "amount": row.get("amount", 0.0),
                })
                total += row.get("amount", 0.0)
        self.amount_total = total
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }


class SubrentPayableWizardLine(models.TransientModel):
    _name = "rental.subrent.payable.wizard.line"
    _description = "Dòng công nợ NCC"

    wizard_id = fields.Many2one("rental.subrent.payable.wizard", ondelete="cascade")
    subrent_contract_id = fields.Many2one("rental.subrent.contract", string="HĐ")
    product_tmpl_id = fields.Many2one("product.template", string="Sản phẩm")
    qty_open = fields.Float(string="SL đang thuê")
    cost_unit = fields.Float(string="Đơn giá / tháng")
    amount = fields.Float(string="Thành tiền")
