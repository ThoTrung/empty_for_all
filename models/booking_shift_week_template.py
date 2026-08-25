# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class BookingShiftWeekTemplate(models.Model):
    _name = "booking.shift.week.template"
    _description = "Mẫu ca làm theo tuần"
    _order = "name, id"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company",
        string="Công ty",
        default=lambda self: self.env.company,
        index=True,
    )
    line_ids = fields.One2many(
        "booking.shift.week.template.line",
        "template_id",
        string="Dòng theo thứ",
    )

    @api.model
    def get_default_active_template(self, company=None):
        company = company or self.env.company
        return self.search(
            [("active", "=", True), ("company_id", "=", company.id)],
            order="id",
            limit=1,
        )

    def action_open_apply_wizard(self):
        self.ensure_one()
        today = fields.Date.context_today(self)
        return {
            "type": "ir.actions.act_window",
            "name": _("Áp dụng mẫu ca"),
            "res_model": "booking.shift.template.apply.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_template_id": self.id,
                "default_date_start": today,
                "default_date_end": today + timedelta(days=27),
            },
        }


class BookingShiftWeekTemplateLine(models.Model):
    _name = "booking.shift.week.template.line"
    _description = "Dòng mẫu ca theo thứ"
    _order = "weekday, shift_start_time_hours, id"

    template_id = fields.Many2one(
        "booking.shift.week.template",
        required=True,
        ondelete="cascade",
        index=True,
    )
    weekday = fields.Selection(
        selection=[
            ("0", "Thứ 2"),
            ("1", "Thứ 3"),
            ("2", "Thứ 4"),
            ("3", "Thứ 5"),
            ("4", "Thứ 6"),
            ("5", "Thứ 7"),
            ("6", "Chủ nhật"),
        ],
        string="Thứ",
        required=True,
    )
    shift_start_time_hours = fields.Float(
        string="Giờ bắt đầu ca",
        default=8.0,
        required=True,
    )
    shift_duration_hours = fields.Float(
        string="Thời lượng ca (giờ)",
        default=10.0,
        required=True,
    )
    user_ids = fields.Many2many(
        "res.users",
        "booking_shift_week_template_line_user_rel",
        "line_id",
        "user_id",
        string="Nhân viên",
        domain=[("share", "=", False)],
    )

    @api.constrains("shift_start_time_hours", "shift_duration_hours")
    def _check_shift_hours(self):
        for rec in self:
            if rec.shift_start_time_hours < 0 or rec.shift_start_time_hours >= 24:
                raise ValidationError(_("Giờ bắt đầu ca phải từ 0 đến dưới 24."))
            if rec.shift_duration_hours < 0:
                raise ValidationError(_("Thời lượng ca không được âm."))


class BookingShiftTemplateApplyWizard(models.TransientModel):
    _name = "booking.shift.template.apply.wizard"
    _description = "Áp dụng mẫu ca tuần"

    MAX_APPLY_DAYS = 90

    template_id = fields.Many2one(
        "booking.shift.week.template",
        string="Mẫu ca",
        required=True,
        domain="[('active', '=', True)]",
    )
    date_start = fields.Date(string="Từ ngày", required=True)
    date_end = fields.Date(string="Đến ngày", required=True)
    overwrite_existing = fields.Boolean(
        string="Ghi đè ngày đã cấu hình ca",
        default=False,
        help="Mặc định bỏ qua ngày đã có dòng ca làm (giữ chỉnh tay / nghỉ lễ).",
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if "template_id" in fields_list and not res.get("template_id"):
            tmpl = self.env["booking.shift.week.template"].get_default_active_template()
            if tmpl:
                res["template_id"] = tmpl.id
        return res

    @api.constrains("date_start", "date_end")
    def _check_dates(self):
        for rec in self:
            if rec.date_start and rec.date_end and rec.date_end < rec.date_start:
                raise ValidationError(_("Đến ngày phải không trước Từ ngày."))
            if rec.date_start and rec.date_end:
                span = (rec.date_end - rec.date_start).days
                if span > self.MAX_APPLY_DAYS:
                    raise ValidationError(
                        _("Khoảng ngày tối đa là %s ngày.", self.MAX_APPLY_DAYS)
                    )

    def action_apply(self):
        self.ensure_one()
        if not self.template_id.line_ids:
            raise UserError(_("Mẫu ca chưa có dòng theo thứ."))
        lines_by_weekday = {}
        for line in self.template_id.line_ids:
            lines_by_weekday.setdefault(line.weekday, []).append(line)

        ShiftConfig = self.env["booking.shift.config"]
        Line = self.env["booking.shift.config.line"]
        applied = 0
        skipped = 0
        day = self.date_start
        while day <= self.date_end:
            weekday_key = str(day.weekday())
            template_lines = lines_by_weekday.get(weekday_key, [])
            if template_lines:
                config = ShiftConfig.get_or_create_for_date(day)
                if config.line_ids and not self.overwrite_existing:
                    skipped += 1
                else:
                    if config.line_ids:
                        config.line_ids.unlink()
                    for tline in template_lines:
                        Line.create(
                            {
                                "config_id": config.id,
                                "name": dict(tline._fields["weekday"].selection).get(
                                    tline.weekday, _("Ca")
                                ),
                                "shift_start_time_hours": tline.shift_start_time_hours,
                                "shift_duration_hours": tline.shift_duration_hours,
                                "user_ids": [(6, 0, tline.user_ids.ids)],
                            }
                        )
                    applied += 1
            day += timedelta(days=1)

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Áp dụng mẫu ca"),
                "message": _(
                    "Đã ghi %s ngày, bỏ qua %s ngày (đã có ca và không ghi đè).",
                    applied,
                    skipped,
                ),
                "type": "success",
                "sticky": False,
            },
        }
