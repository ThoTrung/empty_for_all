from odoo import api, fields, models, _
from odoo.exceptions import UserError


class RentalRejectConfirmWizard(models.TransientModel):
    _name = "rental.reject.confirm.wizard"
    _description = "Reject rental contract confirmation"

    message_reason = fields.Text(string="Lý do không xác nhận", required=True)

    def action_reject(self):
        self.ensure_one()
        ctx = self.env.context or {}
        active_model = ctx.get("active_model")
        active_ids = ctx.get("active_ids") or []
        if active_model != "rental.contract" or not active_ids:
            raise UserError(_("Wizard thiếu ngữ cảnh hợp đồng."))  # noqa: E501

        contract = self.env["rental.contract"].browse(active_ids).ensure_one()
        if contract.status != "need_approve":
            raise UserError(_("Chỉ có thể không xác nhận khi hợp đồng ở trạng thái cần xác nhận."))  # noqa: E501

        # Post reason to chatter so all followers are notified.
        contract.message_post(
            body=_("Không xác nhận hợp đồng thuê.<br/>Lý do: %s") % (self.message_reason,),
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
        )

        contract.with_context(rental_contract_allow_locked_write=True).write({
            "status": "need_fix",
            "edit_unlocked": False,
        })

        return {"type": "ir.actions.act_window_close"}

