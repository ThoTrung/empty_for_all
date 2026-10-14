from markupsafe import Markup

from odoo import fields, models, _
from odoo.tools import float_round


def _format_qty(qty, product):
    """Số lượng theo độ làm tròn ĐVT, bỏ phần thập phân thừa (5.0 → 5)."""
    value = float_round(qty, precision_rounding=product.uom_id.rounding or 1.0)
    if abs(value - round(value)) < 1e-9:
        return str(int(round(value)))
    return f"{value:.3f}".rstrip("0").rstrip(".")


class RrTransportCompleteWizard(models.TransientModel):
    _name = "rr.transport.complete.wizard"
    _description = "Cảnh báo thiếu hàng khi hoàn thành phiếu xuất nhập kho"

    transport_id = fields.Many2one("rr.transport", string="Phiếu", required=True, ondelete="cascade")
    company_id = fields.Many2one(related="transport_id.company_id", store=True, readonly=True)
    message = fields.Html(string="Vật tư thiếu", readonly=True, sanitize=False)

    def _action_open(self, transport, shortages):
        rows = Markup("").join(
            Markup("<tr><td>%s</td><td class='text-end'>%s</td><td class='text-end'>%s</td></tr>")
            % (product.display_name, _format_qty(qty, product), _format_qty(available, product))
            for product, qty, available in shortages
        )
        message = (
            Markup("<p>%s</p>") % _("Kho không đủ hàng cho các vật tư sau. Đồng ý thì phiếu kho vẫn được "
                                    "xác nhận và tồn kho sẽ bị âm.")
            + Markup("<table class='table table-sm'><thead><tr><th>%s</th><th class='text-end'>%s</th>"
                     "<th class='text-end'>%s</th></tr></thead><tbody>%s</tbody></table>")
            % (_("Vật tư"), _("Cần xuất"), _("Tồn kho"), rows)
        )
        wizard = self.create({"transport_id": transport.id, "message": message})
        return {
            "type": "ir.actions.act_window",
            "name": _("Không đủ hàng"),
            "res_model": self._name,
            "res_id": wizard.id,
            "view_mode": "form",
            "views": [(False, "form")],
            "target": "new",
            # Chỉ giữ cờ cần cho bước sau; không kế thừa size_class/active_* của form hợp đồng.
            "context": {
                "rr_transport_from_contract": self.env.context.get("rr_transport_from_contract", False),
            },
        }

    def action_confirm(self):
        self.ensure_one()
        return self.transport_id.with_context(rr_transport_allow_negative=True).action_complete_transport()
