# -*- coding: utf-8 -*-
from odoo import fields, models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    rental_transport_id = fields.Many2one(
        "rr.transport",
        string="Phiếu xuất nhập kho",
        index=True,
        copy=False,
        ondelete="set null",
    )

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
