# -*- coding: utf-8 -*-
from odoo import _, api, fields, models

from odoo.addons.rental_subrent.services.rental_subrent_status_services import (
    shortage_for_product,
)


class SubrentShortageWizard(models.TransientModel):
    _name = "rental.subrent.shortage.wizard"
    _description = "Panel thiếu hàng (tự có + kho thuê ngoài)"

    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    product_id = fields.Many2one("product.product", string="Sản phẩm", required=True)
    qty_needed = fields.Float(string="SL cần giao", required=True, default=1.0)
    owned_qty = fields.Float(string="Tồn kho tự có", readonly=True)
    subrent_wh_qty = fields.Float(string="Kho thuê ngoài", readonly=True)
    available_qty = fields.Float(string="Tổng sẵn sàng", readonly=True)
    shortage_qty = fields.Float(string="Thiếu", readonly=True)
    advice = fields.Text(string="Gợi ý", readonly=True)

    def action_compute(self):
        self.ensure_one()
        data = shortage_for_product(
            self.env, self.product_id, self.qty_needed, self.company_id
        )
        advice = ""
        if data["shortage_qty"] > 0:
            advice = _(
                "Thiếu %(s)s. Gợi ý: tạo phiếu nhận NCC (về kho tạm) hoặc giao thẳng từ NCC."
            ) % {"s": data["shortage_qty"]}
        elif data["subrent_wh_qty"] > 0:
            advice = _("Đủ hàng. Ưu tiên dùng kho tự có trước, rồi lô thuê ngoài còn %(q)s.") % {
                "q": data["subrent_wh_qty"]
            }
        else:
            advice = _("Đủ từ kho tự có.")
        self.write({
            "owned_qty": data["owned_qty"],
            "subrent_wh_qty": data["subrent_wh_qty"],
            "available_qty": data["available_qty"],
            "shortage_qty": data["shortage_qty"],
            "advice": advice,
        })
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }
