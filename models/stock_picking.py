# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.tools.float_utils import float_is_zero


class StockPicking(models.Model):
    _inherit = "stock.picking"

    rental_transport_id = fields.Many2one(
        "rr.transport",
        string="Phiếu xuất nhập kho",
        index=True,
        copy=False,
        ondelete="set null",
    )

    def action_open_form_page(self):
        """Open picking as a full page (not a nested dialog from rr.transport modal)."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.display_name or _("Phiếu kho"),
            "res_model": "stock.picking",
            "view_mode": "form",
            "res_id": self.id,
            "target": "current",
            "context": dict(self.env.context),
        }

    def get_formview_action(self, access_uid=None):
        """From rr.transport: open as page so quantities are editable (not readonly dialog)."""
        action = super().get_formview_action(access_uid=access_uid)
        if self.rental_transport_id:
            action["target"] = "current"
        return action

    def write(self, vals):
        res = super().write(vals)
        # Dự phòng nếu có luồng ghi state trực tiếp (hiếm; state mặc định là computed)
        if vals.get("state") == "done":
            self._rental_sync_transport_done_from_picking()
        return res

    def _action_done(self):
        """`state` của picking là computed từ move — không đi qua write({'state': 'done'}).
        Luồng xác nhận gọi _action_done(); đồng bộ rr.transport tại đây (không phụ thuộc cache state)."""
        res = super()._action_done()
        self._rental_sync_transport_done_from_picking()
        return res

    def _rental_sync_transport_done_from_picking(self):
        """Khi phiếu kho chính (không phải phiếu trả/đảo từ return wizard) được done → transport draft → done."""
        for picking in self:
            transport = picking.rental_transport_id
            if not transport or transport.state != "draft":
                continue
            if picking.return_id:
                continue
            # Ghi trạng thái phiếu vận chuyển với quyền hệ thống để user chỉ cần quyền trên stock.picking
            # (vd. nhóm Người giao/nhận không có perm_write trên rr.transport).
            transport.sudo().write({"state": "done"})

    def _rental_prepare_quantities_for_validate(self):
        """Cho phép xác nhận khi thiếu tồn (xuất âm): bỏ giữ chỗ, điền SL nếu đang 0."""
        for picking in self:
            picking.do_unreserve()
            moves = picking.move_ids.filtered(lambda m: m.state not in ("done", "cancel"))
            for move in moves:
                rounding = move.product_uom.rounding
                if float_is_zero(move.quantity, precision_rounding=rounding) and not float_is_zero(
                    move.product_uom_qty, precision_rounding=rounding
                ):
                    move.quantity = move.product_uom_qty
                if not float_is_zero(move.quantity, precision_rounding=rounding):
                    move.picked = True

    def _rental_action_open_transport(self):
        """Mở lại rr.transport (modal) để UI hiện trạng thái Hoàn thành ngay."""
        self.ensure_one()
        transport = self.rental_transport_id
        if not transport:
            return True
        return {
            "type": "ir.actions.act_window",
            "name": transport.display_name or _("Phiếu xuất nhập kho"),
            "res_model": "rr.transport",
            "view_mode": "form",
            "res_id": transport.id,
            "target": "new",
            "context": dict(self.env.context),
        }

    def button_validate(self):
        rental = self.filtered(lambda p: p.rental_transport_id and not p.return_id)
        other = self - rental
        if other:
            res_other = super(StockPicking, other).button_validate()
            if res_other is not True:
                return res_other
        if not rental:
            return True

        rental._rental_prepare_quantities_for_validate()
        res = super(
            StockPicking,
            rental.with_context(
                skip_sanity_check=True,
                skip_backorder=True,
                cancel_backorder=True,
                skip_sms=True,
                picking_ids_not_to_backorder=rental.ids,
            ),
        ).button_validate()

        # Wizard tương tác (backorder / immediate) → ép hoàn tất, cho phép tồn âm.
        if isinstance(res, dict) and res.get("res_model") in (
            "stock.backorder.confirmation",
            "stock.immediate.transfer",
            "confirm.stock.sms",
        ):
            rental.with_context(cancel_backorder=True, skip_sms=True)._action_done()
            res = True

        if res is not True:
            return res

        # Một phiếu rental: mở lại transport để statusbar cập nhật Hoàn thành.
        if len(rental) == 1:
            return rental._rental_action_open_transport()
        return True
