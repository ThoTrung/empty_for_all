# -*- coding: utf-8 -*-

from odoo.tests.common import tagged, TransactionCase


@tagged('post_install', '-at_install', 'gara_payroll_kpi')
class TestGaraPayrollKpi(TransactionCase):

    def _create_shift_calendar(self, name='Shift Calendar'):
        return self.env['resource.calendar'].create({
            'name': name,
            'company_id': self.env.company.id,
            'attendance_ids': [
                (5, 0, 0),
                (0, 0, {
                    'name': 'Mon Morning',
                    'dayofweek': '0',
                    'hour_from': 8.0,
                    'hour_to': 12.0,
                    'day_period': 'morning',
                }),
                (0, 0, {
                    'name': 'Mon Afternoon',
                    'dayofweek': '0',
                    'hour_from': 13.0,
                    'hour_to': 17.0,
                    'day_period': 'afternoon',
                }),
            ],
        })

    def test_payroll_summary_amounts(self):
        employee = self.env['hr.employee'].create({'name': 'Payroll Employee'})
        group = self.env['gara.salary.grade.group'].create({'name': 'Technician', 'code': 'TECH'})
        grade = self.env['gara.salary.grade'].create({
            'name': 'Level 1',
            'code': 'L1',
            'group_id': group.id,
            'base_salary': 26000000.0,
        })
        summary = self.env['gara.payroll.summary'].create({
            'employee_id': employee.id,
            'period': '2026-04-01',
            'grade_id': grade.id,
            'base_salary': 26000000.0,
            'work_days': 26.0,
            'standard_days': 26.0,
            'allowance_amount': 1000000.0,
            'bonus_amount': 500000.0,
            'penalty_amount': 200000.0,
            'pit_manual_override': True,
            'pit_override_amount': 300000.0,
        })

        self.assertEqual(summary.gross_amount, 27300000.0)
        self.assertEqual(summary.pit_amount, 300000.0)
        self.assertEqual(summary.net_amount, 27000000.0)

    def test_payroll_summary_computes_vietnam_pit(self):
        employee = self.env['hr.employee'].create({'name': 'PIT Employee'})
        summary = self.env['gara.payroll.summary'].create({
            'employee_id': employee.id,
            'period': '2026-04-01',
            'base_salary': 57500000.0,
            'work_days': 26.0,
            'standard_days': 26.0,
        })

        self.assertEqual(summary.gross_amount, 57500000.0)
        self.assertEqual(summary.pit_config_id, self.env.ref('gara_payroll_kpi.gara_pit_config_vn_2026'))
        self.assertEqual(summary.taxable_income, 42000000.0)
        self.assertEqual(summary.pit_amount, 4900000.0)
        self.assertEqual(summary.net_amount, 52600000.0)

    def test_kpi_score(self):
        employee = self.env['hr.employee'].create({'name': 'KPI Employee'})
        indicator = self.env['gara.kpi.indicator'].create({
            'name': 'Revenue',
            'code': 'REV',
            'measure_type': 'amount',
        })
        assignment = self.env['gara.employee.kpi'].create({
            'employee_id': employee.id,
            'period': '2026-04-01',
            'line_ids': [(0, 0, {
                'indicator_id': indicator.id,
                'target_value': 100.0,
                'actual_value': 80.0,
                'weight': 2.0,
            })],
        })

        self.assertEqual(assignment.line_ids.score, 80.0)
        self.assertEqual(assignment.score, 80.0)

    def test_daily_attendance_updates_work_summary(self):
        employee = self.env['hr.employee'].create({'name': 'Attendance Employee'})
        code = self.env['gara.attendance.code'].create({
            'name': 'Full day',
            'code': 'X',
            'paid': True,
            'workday_factor': 1.0,
        })
        attendance = self.env['gara.daily.attendance'].create({
            'employee_id': employee.id,
            'date': '2026-04-10',
            'attendance_code_id': code.id,
            'overtime_hours': 2.5,
        })

        attendance.action_confirm()

        summary = self.env['gara.work.summary'].search([
            ('employee_id', '=', employee.id),
            ('period', '=', '2026-04-01'),
        ], limit=1)
        self.assertTrue(summary)
        self.assertEqual(summary.attendance_code_id, code)
        self.assertEqual(summary.work_days, 1.0)
        self.assertEqual(summary.overtime_hours, 2.5)

        attendance.action_cancel()
        self.assertEqual(summary.work_days, 0.0)
        self.assertEqual(summary.overtime_hours, 0.0)

    def test_leave_request_approval_updates_work_summary(self):
        employee = self.env['hr.employee'].create({'name': 'Leave Employee'})
        request = self.env['gara.leave.request'].create({
            'name': 'Annual leave',
            'employee_id': employee.id,
            'date_from': '2026-04-15',
            'date_to': '2026-04-16',
            'leave_type': 'paid',
        })

        request.action_approve()

        summary = self.env['gara.work.summary'].search([
            ('employee_id', '=', employee.id),
            ('period', '=', '2026-04-01'),
        ], limit=1)
        self.assertTrue(summary)
        self.assertEqual(request.day_count, 2.0)
        self.assertEqual(summary.leave_days, 2.0)

        request.action_refuse()
        self.assertEqual(summary.leave_days, 0.0)

    def test_work_shift_syncs_employee_calendar(self):
        calendar = self._create_shift_calendar('Technician Calendar')
        code = self.env['gara.attendance.code'].create({
            'name': 'Full Day Shift',
            'code': 'X',
            'paid': True,
            'workday_factor': 1.0,
        })
        shift = self.env['gara.work.shift'].create({
            'name': 'Ca HC',
            'code': 'HC',
            'company_id': self.env.company.id,
            'calendar_id': calendar.id,
            'attendance_code_id': code.id,
        })
        employee = self.env['hr.employee'].create({
            'name': 'Shift Employee',
            'gara_work_shift_id': shift.id,
        })

        self.assertEqual(employee.resource_calendar_id, calendar)
        self.assertEqual(employee.gara_work_shift_id, shift)
        self.assertEqual(employee.gara_weekly_hours, 8.0)
        self.assertEqual(shift.hours_per_day, 8.0)
        self.assertEqual(shift.weekly_hours, 8.0)

    def test_daily_attendance_defaults_shift_and_hours(self):
        calendar = self._create_shift_calendar('Attendance Calendar')
        code = self.env['gara.attendance.code'].create({
            'name': 'Shift Present',
            'code': 'X2',
            'paid': True,
            'workday_factor': 1.0,
        })
        shift = self.env['gara.work.shift'].create({
            'name': 'Ca T2',
            'code': 'T2',
            'company_id': self.env.company.id,
            'calendar_id': calendar.id,
            'attendance_code_id': code.id,
        })
        employee = self.env['hr.employee'].create({
            'name': 'Attendance Shift Employee',
            'gara_work_shift_id': shift.id,
        })
        attendance = self.env['gara.daily.attendance'].create({
            'employee_id': employee.id,
            'date': '2026-04-06',
            'check_in': '2026-04-06 01:00:00',
            'check_out': '2026-04-06 09:30:00',
        })

        self.assertEqual(attendance.shift_id, shift)
        self.assertEqual(attendance.attendance_code_id, code)
        self.assertEqual(attendance.planned_hours, 8.0)
        self.assertEqual(attendance.actual_hours, 8.5)
