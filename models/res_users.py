from odoo import models, fields, api


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
        leader_group = self.env.ref("rental.group_rental_leader", raise_if_not_found=False)
        for user in self:
            user.is_rental_leader = bool(
                leader_group and leader_group in user.groups_id
            )

