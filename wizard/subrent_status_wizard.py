# -*- coding: utf-8 -*-
from odoo import _, api, fields, models

from odoo.addons.rental_subrent.services.rental_subrent_status_services import (
    get_subrent_kpis,
)


class SubrentStatusWizard(models.TransientModel):
    _name = "rental.subrent.status.wizard"
    _description = "Tình trạng SP thuê ngoài"

    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    lot_count_open = fields.Integer(string="Số lô đang mở", readonly=True)
    qty_at_subrent_wh = fields.Float(string="SL tại kho thuê ngoài", readonly=True)
    qty_on_customer = fields.Float(string="SL đang ở công trình", readonly=True)
    idle_lot_count = fields.Integer(string="Lô idle (cảnh báo)", readonly=True)
    due_lot_count = fields.Integer(string="Lô đến hạn trả NCC", readonly=True)
    cost_per_day_estimate = fields.Float(
        string="Chi phí ước tính / ngày",
        readonly=True,
        groups="rental_subrent.group_rental_subrent_manager",
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        company = self.env.company
        kpis = get_subrent_kpis(self.env, company_ids=[company.id])
        res.update({
            "company_id": company.id,
            **kpis,
        })
        return res

    def action_refresh(self):
        self.ensure_one()
        kpis = get_subrent_kpis(self.env, company_ids=[self.company_id.id])
        self.write(kpis)
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_open_lots_wh(self):
        return self._open_lots([("qty_at_subrent_wh", ">", 0), ("state", "!=", "closed")])

    def action_open_lots_customer(self):
        return self._open_lots([("qty_on_customer", ">", 0), ("state", "!=", "closed")])

    def action_open_lots_idle(self):
        lots = self.env["rental.subrent.lot"].search([
            ("company_id", "=", self.company_id.id),
            ("state", "!=", "closed"),
        ]).filtered("is_idle_warning")
        return {
            "type": "ir.actions.act_window",
            "name": _("Lô idle"),
            "res_model": "rental.subrent.lot",
            "view_mode": "tree,form",
            "domain": [("id", "in", lots.ids)],
        }

    def action_open_lots_due(self):
        lots = self.env["rental.subrent.lot"].search([
            ("company_id", "=", self.company_id.id),
            ("state", "!=", "closed"),
        ]).filtered("is_due_return")
        return {
            "type": "ir.actions.act_window",
            "name": _("Đến hạn trả NCC"),
            "res_model": "rental.subrent.lot",
            "view_mode": "tree,form",
            "domain": [("id", "in", lots.ids)],
        }

    def _open_lots(self, domain):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Lô thuê ngoài"),
            "res_model": "rental.subrent.lot",
            "view_mode": "tree,kanban,form",
            "domain": [("company_id", "=", self.company_id.id)] + domain,
        }
