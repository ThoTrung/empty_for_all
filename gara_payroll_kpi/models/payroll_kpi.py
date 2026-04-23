# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class GaraSalaryMinimum(models.Model):
    _name = 'gara.salary.minimum'
    _description = 'Gara Minimum Wage'
    _order = 'date_from desc, id desc'

    name = fields.Char(required=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, required=True)
    date_from = fields.Date(required=True)
    amount = fields.Monetary(required=True)
    currency_id = fields.Many2one(related='company_id.currency_id', readonly=True)
    active = fields.Boolean(default=True)


class GaraSalaryGradeGroup(models.Model):
    _name = 'gara.salary.grade.group'
    _description = 'Gara Salary Grade Group'
    _order = 'sequence, name'

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)


class GaraSalaryGrade(models.Model):
    _name = 'gara.salary.grade'
    _description = 'Gara Salary Grade'
    _order = 'group_id, sequence, name'

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    group_id = fields.Many2one('gara.salary.grade.group', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    base_salary = fields.Monetary(required=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, required=True)
    currency_id = fields.Many2one(related='company_id.currency_id', readonly=True)
    active = fields.Boolean(default=True)


class GaraAllowanceType(models.Model):
    _name = 'gara.allowance.type'
    _description = 'Gara Allowance Type'
    _order = 'sequence, name'

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    taxable = fields.Boolean(default=True)
    active = fields.Boolean(default=True)


class GaraEmployeeAllowance(models.Model):
    _name = 'gara.employee.allowance'
    _description = 'Gara Employee Allowance'
    _order = 'employee_id, allowance_type_id'

    employee_id = fields.Many2one('hr.employee', required=True)
    allowance_type_id = fields.Many2one('gara.allowance.type', required=True)
    amount = fields.Monetary(required=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, required=True)
    currency_id = fields.Many2one(related='company_id.currency_id', readonly=True)
    active = fields.Boolean(default=True)


class GaraBonusPenalty(models.Model):
    _name = 'gara.bonus.penalty'
    _description = 'Gara Bonus/Penalty'
    _order = 'date desc, id desc'

    name = fields.Char(required=True)
    employee_id = fields.Many2one('hr.employee', required=True)
    date = fields.Date(default=fields.Date.context_today, required=True)
    type = fields.Selection([('bonus', 'Bonus'), ('penalty', 'Penalty')], default='bonus', required=True)
    amount = fields.Monetary(required=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, required=True)
    currency_id = fields.Many2one(related='company_id.currency_id', readonly=True)
    note = fields.Text()


class GaraAttendanceCode(models.Model):
    _name = 'gara.attendance.code'
    _description = 'Gara Attendance Code'
    _order = 'sequence, code'

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    paid = fields.Boolean(default=True)
    workday_factor = fields.Float(default=1.0)
    active = fields.Boolean(default=True)


class GaraPitConfig(models.Model):
    _name = 'gara.pit.config'
    _description = 'Gara PIT Configuration'
    _order = 'date_from desc, id desc'

    name = fields.Char(required=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, required=True)
    date_from = fields.Date(required=True)
    personal_deduction = fields.Monetary(required=True)
    dependent_deduction = fields.Monetary(required=True)
    bracket_ids = fields.One2many('gara.pit.bracket', 'config_id')
    currency_id = fields.Many2one(related='company_id.currency_id', readonly=True)
    active = fields.Boolean(default=True)

    @api.model
    def _get_config_for_period(self, period, company):
        return self.search([
            ('company_id', '=', company.id),
            ('date_from', '<=', period),
            ('active', '=', True),
        ], limit=1)

    def _compute_monthly_pit(self, taxable_income):
        self.ensure_one()
        remaining = max(taxable_income, 0.0)
        total_tax = 0.0
        for bracket in self.bracket_ids.sorted('sequence'):
            lower = bracket.lower_limit
            upper = bracket.upper_limit or taxable_income
            taxable_part = max(min(remaining, upper - lower), 0.0)
            total_tax += taxable_part * bracket.rate / 100.0
            remaining -= taxable_part
            if remaining <= 0.0:
                break
        return total_tax


class GaraPitBracket(models.Model):
    _name = 'gara.pit.bracket'
    _description = 'Gara PIT Bracket'
    _order = 'config_id, sequence, lower_limit'

    config_id = fields.Many2one('gara.pit.config', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    name = fields.Char(required=True)
    lower_limit = fields.Monetary(required=True)
    upper_limit = fields.Monetary(help='Leave empty or zero for the final open-ended bracket.')
    rate = fields.Float(required=True)
    currency_id = fields.Many2one(related='config_id.currency_id', readonly=True)

    @api.constrains('lower_limit', 'upper_limit', 'rate')
    def _check_limits(self):
        for bracket in self:
            if bracket.lower_limit < 0.0:
                raise ValidationError(_('Lower limit must be positive.'))
            if bracket.upper_limit and bracket.upper_limit <= bracket.lower_limit:
                raise ValidationError(_('Upper limit must be greater than lower limit.'))
            if bracket.rate < 0.0:
                raise ValidationError(_('Tax rate must be positive.'))


class GaraDailyAttendance(models.Model):
    _name = 'gara.daily.attendance'
    _description = 'Gara Daily Attendance'
    _order = 'date desc, employee_id'

    employee_id = fields.Many2one('hr.employee', required=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, required=True)
    date = fields.Date(default=fields.Date.context_today, required=True)
    attendance_code_id = fields.Many2one('gara.attendance.code', required=True)
    check_in = fields.Datetime()
    check_out = fields.Datetime()
    work_days = fields.Float(compute='_compute_work_amounts', store=True)
    overtime_hours = fields.Float(default=0.0)
    state = fields.Selection(
        [('draft', 'Draft'), ('confirmed', 'Confirmed'), ('cancel', 'Cancelled')],
        default='draft',
        required=True,
    )
    note = fields.Text()

    @api.depends('attendance_code_id', 'state')
    def _compute_work_amounts(self):
        for attendance in self:
            attendance.work_days = (
                attendance.attendance_code_id.workday_factor
                if attendance.state == 'confirmed' and attendance.attendance_code_id.paid
                else 0.0
            )

    def _period_key(self):
        self.ensure_one()
        return fields.Date.to_date(self.date).replace(day=1)

    def _affected_keys(self):
        return {(attendance.employee_id.id, attendance._period_key()) for attendance in self if attendance.employee_id and attendance.date}

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._recompute_work_summaries(records._affected_keys())
        return records

    def write(self, vals):
        keys = self._affected_keys()
        result = super().write(vals)
        keys |= self._affected_keys()
        self._recompute_work_summaries(keys)
        return result

    def unlink(self):
        keys = self._affected_keys()
        result = super().unlink()
        self._recompute_work_summaries(keys)
        return result

    def action_confirm(self):
        self.write({'state': 'confirmed'})

    def action_cancel(self):
        self.write({'state': 'cancel'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})

    def _recompute_work_summaries(self, keys):
        for employee_id, period in keys:
            self.env['gara.work.summary']._recompute_employee_period(employee_id, period)


class GaraLeaveRequest(models.Model):
    _name = 'gara.leave.request'
    _description = 'Gara Leave Request'
    _order = 'date_from desc, employee_id'

    name = fields.Char(required=True)
    employee_id = fields.Many2one('hr.employee', required=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, required=True)
    date_from = fields.Date(required=True)
    date_to = fields.Date(required=True)
    leave_type = fields.Selection(
        [('paid', 'Paid Leave'), ('unpaid', 'Unpaid Leave'), ('sick', 'Sick Leave'), ('other', 'Other')],
        default='paid',
        required=True,
    )
    day_count = fields.Float(compute='_compute_day_count', store=True)
    state = fields.Selection(
        [('draft', 'Draft'), ('approved', 'Approved'), ('refused', 'Refused'), ('cancel', 'Cancelled')],
        default='draft',
        required=True,
    )
    note = fields.Text()

    @api.depends('date_from', 'date_to')
    def _compute_day_count(self):
        for request in self:
            if request.date_from and request.date_to and request.date_to >= request.date_from:
                request.day_count = (request.date_to - request.date_from).days + 1
            else:
                request.day_count = 0.0

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for request in self:
            if request.date_from and request.date_to and request.date_to < request.date_from:
                raise ValidationError(_('Date To must be after Date From.'))

    def _affected_keys(self):
        keys = set()
        for request in self:
            if not request.employee_id or not request.date_from or not request.date_to:
                continue
            current = fields.Date.to_date(request.date_from).replace(day=1)
            end = fields.Date.to_date(request.date_to).replace(day=1)
            while current <= end:
                keys.add((request.employee_id.id, current))
                if current.month == 12:
                    current = current.replace(year=current.year + 1, month=1)
                else:
                    current = current.replace(month=current.month + 1)
        return keys

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._recompute_work_summaries(records._affected_keys())
        return records

    def write(self, vals):
        keys = self._affected_keys()
        result = super().write(vals)
        keys |= self._affected_keys()
        self._recompute_work_summaries(keys)
        return result

    def unlink(self):
        keys = self._affected_keys()
        result = super().unlink()
        self._recompute_work_summaries(keys)
        return result

    def action_approve(self):
        self.write({'state': 'approved'})

    def action_refuse(self):
        self.write({'state': 'refused'})

    def action_cancel(self):
        self.write({'state': 'cancel'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})

    def _recompute_work_summaries(self, keys):
        for employee_id, period in keys:
            self.env['gara.work.summary']._recompute_employee_period(employee_id, period)


class GaraWorkSummary(models.Model):
    _name = 'gara.work.summary'
    _description = 'Gara Work Summary'
    _order = 'period desc, employee_id'

    employee_id = fields.Many2one('hr.employee', required=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, required=True)
    period = fields.Date(required=True)
    attendance_code_id = fields.Many2one('gara.attendance.code')
    work_days = fields.Float(default=0.0)
    leave_days = fields.Float(default=0.0)
    overtime_hours = fields.Float(default=0.0)

    _sql_constraints = [
        ('employee_period_unique', 'unique(employee_id, period)', 'A work summary already exists for this employee and period.'),
    ]

    @api.model
    def _month_range(self, period):
        start = fields.Date.to_date(period).replace(day=1)
        if start.month == 12:
            end = start.replace(year=start.year + 1, month=1)
        else:
            end = start.replace(month=start.month + 1)
        return start, end

    @api.model
    def _leave_days_in_period(self, leave, start, end):
        date_from = max(fields.Date.to_date(leave.date_from), start)
        date_to = min(fields.Date.to_date(leave.date_to), end)
        return (date_to - date_from).days + 1 if date_to >= date_from else 0.0

    @api.model
    def _recompute_employee_period(self, employee_id, period):
        start, next_month = self._month_range(period)
        end = next_month - timedelta(days=1)
        attendances = self.env['gara.daily.attendance'].search([
            ('employee_id', '=', employee_id),
            ('date', '>=', start),
            ('date', '<', next_month),
            ('state', '=', 'confirmed'),
        ])
        leaves = self.env['gara.leave.request'].search([
            ('employee_id', '=', employee_id),
            ('date_from', '<=', end),
            ('date_to', '>=', start),
            ('state', '=', 'approved'),
        ])
        summary = self.search([('employee_id', '=', employee_id), ('period', '=', start)], limit=1)
        values = {
            'employee_id': employee_id,
            'company_id': self.env.company.id,
            'period': start,
            'attendance_code_id': attendances[:1].attendance_code_id.id,
            'work_days': sum(attendances.mapped('work_days')),
            'leave_days': sum(self._leave_days_in_period(leave, start, end) for leave in leaves),
            'overtime_hours': sum(attendances.mapped('overtime_hours')),
        }
        if summary:
            summary.write(values)
        else:
            summary = self.create(values)
        return summary


class GaraKpiIndicator(models.Model):
    _name = 'gara.kpi.indicator'
    _description = 'Gara KPI Indicator'
    _order = 'sequence, code'

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    measure_type = fields.Selection(
        [('number', 'Number'), ('amount', 'Amount'), ('percent', 'Percent')],
        default='number',
        required=True,
    )
    active = fields.Boolean(default=True)


class GaraKpiTemplate(models.Model):
    _name = 'gara.kpi.template'
    _description = 'Gara KPI Template'
    _order = 'sequence, name'

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    line_ids = fields.One2many('gara.kpi.template.line', 'template_id')
    active = fields.Boolean(default=True)


class GaraKpiTemplateLine(models.Model):
    _name = 'gara.kpi.template.line'
    _description = 'Gara KPI Template Line'
    _order = 'sequence, id'

    template_id = fields.Many2one('gara.kpi.template', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    indicator_id = fields.Many2one('gara.kpi.indicator', required=True)
    target_value = fields.Float(default=0.0)
    weight = fields.Float(default=1.0)


class GaraEmployeeKpi(models.Model):
    _name = 'gara.employee.kpi'
    _description = 'Gara Employee KPI Assignment'
    _order = 'period desc, employee_id'

    employee_id = fields.Many2one('hr.employee', required=True)
    period = fields.Date(required=True)
    template_id = fields.Many2one('gara.kpi.template')
    line_ids = fields.One2many('gara.employee.kpi.line', 'assignment_id')
    score = fields.Float(compute='_compute_score', store=True)
    state = fields.Selection([('draft', 'Draft'), ('confirmed', 'Confirmed'), ('done', 'Done')], default='draft')

    @api.onchange('template_id')
    def _onchange_template_id(self):
        for rec in self:
            rec.line_ids = [(5, 0, 0)] + [
                (0, 0, {
                    'indicator_id': line.indicator_id.id,
                    'target_value': line.target_value,
                    'weight': line.weight,
                })
                for line in rec.template_id.line_ids
            ]

    @api.depends('line_ids.score', 'line_ids.weight')
    def _compute_score(self):
        for rec in self:
            total_weight = sum(rec.line_ids.mapped('weight'))
            rec.score = sum(line.score * line.weight for line in rec.line_ids) / total_weight if total_weight else 0.0


class GaraEmployeeKpiLine(models.Model):
    _name = 'gara.employee.kpi.line'
    _description = 'Gara Employee KPI Line'
    _order = 'assignment_id, sequence, id'

    assignment_id = fields.Many2one('gara.employee.kpi', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    indicator_id = fields.Many2one('gara.kpi.indicator', required=True)
    target_value = fields.Float(default=0.0)
    actual_value = fields.Float(default=0.0)
    weight = fields.Float(default=1.0)
    score = fields.Float(compute='_compute_score', store=True)

    @api.depends('target_value', 'actual_value')
    def _compute_score(self):
        for line in self:
            line.score = min((line.actual_value / line.target_value) * 100.0, 100.0) if line.target_value else 0.0


class GaraPayrollSummary(models.Model):
    _name = 'gara.payroll.summary'
    _description = 'Gara Payroll Summary'
    _order = 'period desc, employee_id'

    employee_id = fields.Many2one('hr.employee', required=True)
    period = fields.Date(required=True)
    grade_id = fields.Many2one('gara.salary.grade')
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, required=True)
    currency_id = fields.Many2one(related='company_id.currency_id', readonly=True)
    base_salary = fields.Monetary()
    work_days = fields.Float(default=0.0)
    standard_days = fields.Float(default=26.0)
    allowance_amount = fields.Monetary()
    bonus_amount = fields.Monetary()
    penalty_amount = fields.Monetary()
    insurance_deduction = fields.Monetary(string='Insurance Deduction')
    other_tax_deduction = fields.Monetary(string='Other Tax Deduction')
    dependent_count = fields.Integer(default=0)
    pit_config_id = fields.Many2one('gara.pit.config', compute='_compute_pit_amounts', store=True)
    taxable_income = fields.Monetary(compute='_compute_pit_amounts', store=True)
    pit_manual_override = fields.Boolean(string='Manual PIT')
    pit_override_amount = fields.Monetary(string='Manual PIT Amount')
    pit_amount = fields.Monetary(string='PIT', compute='_compute_pit_amounts', store=True)
    gross_amount = fields.Monetary(compute='_compute_amounts', store=True)
    net_amount = fields.Monetary(compute='_compute_pit_amounts', store=True)

    @api.onchange('grade_id')
    def _onchange_grade_id(self):
        for rec in self:
            rec.base_salary = rec.grade_id.base_salary

    @api.depends('base_salary', 'work_days', 'standard_days', 'allowance_amount', 'bonus_amount', 'penalty_amount')
    def _compute_amounts(self):
        for rec in self:
            prorated = rec.base_salary * rec.work_days / rec.standard_days if rec.standard_days else 0.0
            rec.gross_amount = prorated + rec.allowance_amount + rec.bonus_amount - rec.penalty_amount

    @api.depends(
        'period',
        'company_id',
        'gross_amount',
        'insurance_deduction',
        'other_tax_deduction',
        'dependent_count',
        'pit_manual_override',
        'pit_override_amount',
    )
    def _compute_pit_amounts(self):
        pit_config_model = self.env['gara.pit.config']
        for rec in self:
            config = pit_config_model._get_config_for_period(rec.period, rec.company_id) if rec.period and rec.company_id else False
            rec.pit_config_id = config
            personal_deduction = config.personal_deduction if config else 0.0
            dependent_deduction = config.dependent_deduction * max(rec.dependent_count, 0) if config else 0.0
            rec.taxable_income = max(
                rec.gross_amount
                - rec.insurance_deduction
                - rec.other_tax_deduction
                - personal_deduction
                - dependent_deduction,
                0.0,
            )
            rec.pit_amount = rec.pit_override_amount if rec.pit_manual_override else (
                config._compute_monthly_pit(rec.taxable_income) if config else 0.0
            )
            rec.net_amount = rec.gross_amount - rec.insurance_deduction - rec.pit_amount
            rec.net_amount = rec.gross_amount - rec.pit_amount
