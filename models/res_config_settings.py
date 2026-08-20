# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    spa_zalo_reminder_enabled = fields.Boolean(
        string="Bật nhắc lịch KH qua Zalo (ZNS)",
        config_parameter="spa_zalo_oa.reminder_enabled",
    )
    spa_zalo_reminder_template_id = fields.Char(
        string="ZNS Template ID nhắc lịch",
        config_parameter="spa_zalo_oa.reminder_template_id",
    )
    spa_zalo_reminder_offset_value = fields.Integer(
        string="Nhắc trước",
        default=2,
        config_parameter="spa_zalo_oa.reminder_offset_value",
    )
    spa_zalo_reminder_offset_unit = fields.Selection(
        selection=[("hours", "Giờ"), ("days", "Ngày")],
        string="Đơn vị nhắc trước",
        default="hours",
        config_parameter="spa_zalo_oa.reminder_offset_unit",
    )
    spa_zalo_batch_size = fields.Integer(
        string="Số tin gửi mỗi lượt cron",
        default=50,
        config_parameter="spa_zalo_oa.batch_size",
    )
    spa_zalo_max_retry = fields.Integer(
        string="Số lần thử lại tối đa",
        default=3,
        config_parameter="spa_zalo_oa.max_retry",
    )
    spa_zalo_development_mode = fields.Boolean(
        string="Chế độ gửi thử Zalo (development)",
        config_parameter="spa_zalo_oa.development_mode",
        help="Gửi với mode=development: chỉ admin OA/App nhận được, không tính phí. "
        "Tắt trên production khi smoke SĐT khách (không phải admin OA).",
    )
    spa_zalo_whitelist_enabled = fields.Boolean(
        string="Chế độ whitelist (chỉ gửi cho SĐT trong danh sách)",
        config_parameter="spa_zalo_oa.whitelist_enabled",
    )
    spa_zalo_whitelist_phones = fields.Char(
        string="Danh sách SĐT whitelist",
        config_parameter="spa_zalo_oa.whitelist_phones",
        help="Phân tách bằng dấu phẩy. Production: bật whitelist 1–2 số trước khi "
        "bật nhắc lịch; chỉ tắt whitelist khi đã ổn. Ngoài danh sách không bị "
        "đánh dấu đã nhắc. Khi bật development, các số này phải là admin OA/App.",
    )
    spa_zalo_reminder_template_keys = fields.Char(
        string="Map khóa template ZNS (JSON)",
        config_parameter="spa_zalo_oa.reminder_template_keys",
        help='Đổi tên khóa nội bộ name/date/time/service sang khóa mẫu Zalo. '
        'Ví dụ: {"name": "customer_name"}. Để trống = dùng đúng 4 khóa mặc định.',
    )
    spa_zalo_oa_account_id = fields.Many2one(
        "spa.zalo.oa.account",
        string="Tài khoản Zalo OA",
        compute="_compute_spa_zalo_oa_account_id",
        readonly=True,
    )

    @api.depends("company_id")
    def _compute_spa_zalo_oa_account_id(self):
        account = self.env["spa.zalo.oa.account"]._get_default()
        for rec in self:
            rec.spa_zalo_oa_account_id = account
