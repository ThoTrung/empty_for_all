# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class GaraWorkShift(models.Model):
    _name = 'gara.work.shift'
    _description = 'Gara Work Shift'
    _order = 'sequence, code, name'

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one(
        'res.company',
        default=lambda self: self.env.company,
        required=True,
    )
    calendar_id = fields.Many2one(
        'resource.calendar',
        required=True,
        check_company=True,
        domain="[('company_id', '=', company_id)]",
    )
    attendance_code_id = fields.Many2one('gara.attendance.code')
    hours_per_day = fields.Float(
        string='Hours per Day',
        related='calendar_id.hours_per_day',
        readonly=True,
    )
    weekly_hours = fields.Float(
        string='Weekly Hours',
        compute='_compute_weekly_hours',
        readonly=True,
    )
    active = fields.Boolean(default=True)
    note = fields.Text()

    _sql_constraints = [
        ('code_company_unique', 'unique(code, company_id)', 'Shift code must be unique per company.'),
    ]

    @api.depends(
        'calendar_id',
        'calendar_id.two_weeks_calendar',
        'calendar_id.attendance_ids',
        'calendar_id.attendance_ids.hour_from',
        'calendar_id.attendance_ids.hour_to',
        'calendar_id.attendance_ids.day_period',
        'calendar_id.attendance_ids.display_type',
        'calendar_id.attendance_ids.week_type',
    )
    def _compute_weekly_hours(self):
        for shift in self:
            shift.weekly_hours = shift._gara_calendar_weekly_hours(shift.calendar_id)

    def _gara_calendar_weekly_hours(self, calendar):
        if not calendar:
            return 0.0
        attendances = calendar.attendance_ids.filtered(
            lambda att: (
                not att.display_type
                and not att.resource_id
                and att.day_period != 'lunch'
            )
        )
        hours = sum(max(att.hour_to - att.hour_from, 0.0) for att in attendances)
        if calendar.two_weeks_calendar and attendances:
            return hours / 2.0
        return hours

    def name_get(self):
        result = []
        for shift in self:
            display = '[%s] %s' % (shift.code, shift.name) if shift.code else shift.name
            result.append((shift.id, display))
        return result

    def action_open_calendar(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Working Time'),
            'res_model': 'resource.calendar',
            'view_mode': 'form',
            'res_id': self.calendar_id.id,
        }


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    gara_employee_code = fields.Char(string='Gara Employee Code', copy=False, index=True)
    gara_salary_grade_id = fields.Many2one(
        'gara.salary.grade',
        string='Gara Salary Grade',
        check_company=True,
    )
    gara_work_shift_id = fields.Many2one(
        'gara.work.shift',
        string='Gara Work Shift',
        check_company=True,
        domain="[('company_id', '=', company_id), ('active', '=', True)]",
    )
    gara_weekly_hours = fields.Float(
        string='Weekly Working Hours',
        compute='_compute_gara_weekly_hours',
        readonly=True,
    )

    _sql_constraints = [
        (
            'gara_employee_code_company_unique',
            'unique(gara_employee_code, company_id)',
            'Gara employee code must be unique per company.',
        ),
    ]

    @api.depends(
        'gara_work_shift_id.weekly_hours',
        'resource_calendar_id',
        'resource_calendar_id.two_weeks_calendar',
        'resource_calendar_id.attendance_ids',
        'resource_calendar_id.attendance_ids.hour_from',
        'resource_calendar_id.attendance_ids.hour_to',
        'resource_calendar_id.attendance_ids.day_period',
        'resource_calendar_id.attendance_ids.display_type',
        'resource_calendar_id.attendance_ids.week_type',
    )
    def _compute_gara_weekly_hours(self):
        for employee in self:
            if employee.gara_work_shift_id:
                employee.gara_weekly_hours = employee.gara_work_shift_id.weekly_hours
            else:
                employee.gara_weekly_hours = self.env['gara.work.shift']._gara_calendar_weekly_hours(
                    employee.resource_calendar_id
                )

    @api.onchange('gara_work_shift_id')
    def _onchange_gara_work_shift_id(self):
        for employee in self:
            if employee.gara_work_shift_id:
                employee.resource_calendar_id = employee.gara_work_shift_id.calendar_id

    @api.model_create_multi
    def create(self, vals_list):
        self._gara_apply_shift_calendar_defaults(vals_list)
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('gara_work_shift_id') and not vals.get('resource_calendar_id'):
            shift = self.env['gara.work.shift'].browse(vals['gara_work_shift_id'])
            vals = dict(vals, resource_calendar_id=shift.calendar_id.id)
        return super().write(vals)

    def _gara_apply_shift_calendar_defaults(self, vals_list):
        for vals in vals_list:
            shift_id = vals.get('gara_work_shift_id')
            if shift_id and not vals.get('resource_calendar_id'):
                shift = self.env['gara.work.shift'].browse(shift_id)
                vals['resource_calendar_id'] = shift.calendar_id.id


class GaraDailyAttendance(models.Model):
    _inherit = 'gara.daily.attendance'

    shift_id = fields.Many2one(
        'gara.work.shift',
        check_company=True,
        domain="[('company_id', '=', company_id), ('active', '=', True)]",
    )
    planned_hours = fields.Float(
        compute='_compute_shift_hours',
        store=True,
        readonly=True,
    )
    actual_hours = fields.Float(
        compute='_compute_actual_hours',
        store=True,
        readonly=True,
    )

    @api.depends(
        'shift_id',
        'date',
        'shift_id.calendar_id',
        'shift_id.calendar_id.two_weeks_calendar',
        'shift_id.calendar_id.attendance_ids',
        'shift_id.calendar_id.attendance_ids.dayofweek',
        'shift_id.calendar_id.attendance_ids.day_period',
        'shift_id.calendar_id.attendance_ids.display_type',
        'shift_id.calendar_id.attendance_ids.week_type',
        'shift_id.calendar_id.attendance_ids.hour_from',
        'shift_id.calendar_id.attendance_ids.hour_to',
        'shift_id.calendar_id.attendance_ids.date_from',
        'shift_id.calendar_id.attendance_ids.date_to',
    )
    def _compute_shift_hours(self):
        for attendance in self:
            attendance.planned_hours = attendance._gara_get_planned_hours()

    @api.depends('check_in', 'check_out')
    def _compute_actual_hours(self):
        for attendance in self:
            if attendance.check_in and attendance.check_out and attendance.check_out > attendance.check_in:
                delta = fields.Datetime.to_datetime(attendance.check_out) - fields.Datetime.to_datetime(attendance.check_in)
                attendance.actual_hours = delta.total_seconds() / 3600.0
            else:
                attendance.actual_hours = 0.0

    @api.onchange('employee_id', 'date')
    def _onchange_employee_date_set_shift(self):
        for attendance in self:
            if attendance.employee_id:
                attendance.shift_id = attendance.employee_id.gara_work_shift_id
                if (
                    attendance.shift_id
                    and attendance.shift_id.attendance_code_id
                    and not attendance.attendance_code_id
                ):
                    attendance.attendance_code_id = attendance.shift_id.attendance_code_id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            employee_id = vals.get('employee_id')
            if employee_id and not vals.get('shift_id'):
                employee = self.env['hr.employee'].browse(employee_id)
                if employee.gara_work_shift_id:
                    vals['shift_id'] = employee.gara_work_shift_id.id
            if vals.get('shift_id') and not vals.get('attendance_code_id'):
                shift = self.env['gara.work.shift'].browse(vals['shift_id'])
                if shift.attendance_code_id:
                    vals['attendance_code_id'] = shift.attendance_code_id.id
        return super().create(vals_list)

    def _gara_get_planned_hours(self):
        self.ensure_one()
        if not self.shift_id or not self.date:
            return 0.0
        calendar = self.shift_id.calendar_id
        target_date = fields.Date.to_date(self.date)
        dayofweek = str(target_date.weekday())
        attendances = calendar.attendance_ids.filtered(
            lambda att: (
                not att.display_type
                and not att.resource_id
                and att.day_period != 'lunch'
                and att.dayofweek == dayofweek
                and (not att.date_from or att.date_from <= target_date)
                and (not att.date_to or att.date_to >= target_date)
            )
        )
        if calendar.two_weeks_calendar:
            week_type = str(self.env['resource.calendar.attendance'].get_week_type(target_date))
            attendances = attendances.filtered(lambda att: not att.week_type or att.week_type == week_type)
        return sum(max(att.hour_to - att.hour_from, 0.0) for att in attendances)
