from odoo import api, fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    is_rental_leader = fields.Boolean(
        string="Là leader cho thuê",
        help="Tự động đánh dấu nếu user thuộc nhóm Rental Leader.",
        compute="_compute_is_rental_leader",
        store=True,
    )
    rental_leader_id = fields.Many2one(
        "res.users",
        string="Leader phụ trách hợp đồng",
        help="Leader sẽ nhận thông báo khi nhân viên yêu cầu xác nhận hợp đồng.",
    )

    @api.depends("groups_id")
    def _compute_is_rental_leader(self):
        leader_group = self.env.ref(
            "rental.group_rental_leader", raise_if_not_found=False
        )
        for user in self:
            user.is_rental_leader = bool(
                leader_group and leader_group in user.groups_id
            )

    def _rental_dashboard_home_action(self):
        return self.env.ref(
            "rental.action_rental_analytics_dashboard",
            raise_if_not_found=False,
        )

    def _rental_sync_home_dashboard(self):
        """Staff (+ implied) land on Dashboard; clear if staff is removed."""
        dashboard = self._rental_dashboard_home_action()
        if not dashboard:
            return
        staff_group = self.env.ref(
            "rental.group_rental_staff", raise_if_not_found=False
        )
        if not staff_group:
            return
        for user in self:
            is_staff = staff_group in user.groups_id
            if is_staff:
                if user.action_id != dashboard:
                    user.sudo().write({"action_id": dashboard.id})
            elif user.action_id == dashboard:
                user.sudo().write({"action_id": False})

    @api.model_create_multi
    def create(self, vals_list):
        users = super().create(vals_list)
        users._rental_sync_home_dashboard()
        return users

    def write(self, vals):
        res = super().write(vals)
        if "groups_id" in vals:
            self._rental_sync_home_dashboard()
        return res
