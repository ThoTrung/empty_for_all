# -*- coding: utf-8 -*-

import base64
import io
import zipfile

from odoo.tests import tagged
from odoo.exceptions import UserError, ValidationError

from odoo.addons.repair import _create_warehouse_data
from odoo.addons.sale.tests.common import TestSaleCommon


@tagged('post_install', '-at_install', 'gara_workshop')
class TestGaraWorkshop(TestSaleCommon):

    @classmethod
    def setUpClass(cls, chart_template_ref=None):
        super().setUpClass(chart_template_ref=chart_template_ref)
        _create_warehouse_data(cls.env)
        cls.env.user.groups_id |= cls.env.ref('gara_workshop.group_gara_workshop_manager')
        cls.env.user.groups_id |= cls.env.ref('gara_workshop.group_gara_role_manager')
        cls.env.user.groups_id |= cls.env.ref('fleet.fleet_group_user')
        cls.env.user.groups_id |= cls.env.ref('sales_team.group_sale_salesman')
        cls.env.user.groups_id |= cls.env.ref('account.group_account_user')

    def _create_vehicle(self):
        brand = self.env['fleet.vehicle.model.brand'].create({'name': 'GBrand'})
        model = self.env['fleet.vehicle.model'].create({
            'brand_id': brand.id,
            'name': 'GModel',
        })
        return self.env['fleet.vehicle'].create({
            'model_id': model.id,
            'license_plate': 'G-UNIT-1',
            'company_id': self.company_data['company'].id,
        })

    def test_case_sequence_and_intake(self):
        vehicle = self._create_vehicle()
        case = self.env['gara.workshop.case'].create({
            'partner_id': self.partner_a.id,
            'vehicle_id': vehicle.id,
            'company_id': self.company_data['company'].id,
        })
        self.assertRegex(case.name, r'^GWC/')
        case.action_set_intake()
        self.assertEqual(case.state, 'intake')

    def test_credit_reversal_preserves_gara_case(self):
        vehicle = self._create_vehicle()
        case = self.env['gara.workshop.case'].create({
            'partner_id': self.partner_a.id,
            'vehicle_id': vehicle.id,
            'company_id': self.company_data['company'].id,
        })
        case.action_create_quotation()
        case.action_confirm_sale()
        inv = case.action_create_invoice()
        self.assertTrue(inv)
        move = inv[0]
        self.assertEqual(move.gara_case_id, case)
        move.action_post()
        rev = move._reverse_moves(cancel=False)
        self.assertEqual(rev.gara_case_id, case)
        product_lines = rev.line_ids.filtered(lambda l: l.display_type == 'product')
        if product_lines:
            self.assertEqual(product_lines[0].gara_case_id, case)

    def test_quotation_confirm_and_invoice_links_case(self):
        vehicle = self._create_vehicle()
        case = self.env['gara.workshop.case'].create({
            'partner_id': self.partner_a.id,
            'vehicle_id': vehicle.id,
            'company_id': self.company_data['company'].id,
        })
        case.action_set_intake()
        so = case.action_create_quotation()
        self.assertEqual(so.gara_case_id, case)
        self.assertEqual(case.state, 'quoted')
        case.action_confirm_sale()
        self.assertEqual(case.state, 'repair')
        moves = case.action_create_invoice()
        self.assertTrue(moves)
        self.assertEqual(moves[0].gara_case_id, case)
        self.assertEqual(case.state, 'invoiced')

    def test_payment_lines_estimate_without_invoice(self):
        vehicle = self._create_vehicle()
        case = self.env['gara.workshop.case'].create({
            'partner_id': self.partner_a.id,
            'vehicle_id': vehicle.id,
            'company_id': self.company_data['company'].id,
        })
        case.action_create_quotation()
        case.action_confirm_sale()
        total = case.sale_order_id.amount_total
        case.action_register_payment_line(total / 2)
        case.invalidate_recordset()
        self.assertAlmostEqual(case.amount_payment_registered, total / 2)
        self.assertAlmostEqual(case.amount_due_estimate, total / 2)

    def test_repair_done_updates_case_state(self):
        vehicle = self._create_vehicle()
        case = self.env['gara.workshop.case'].create({
            'partner_id': self.partner_a.id,
            'vehicle_id': vehicle.id,
            'company_id': self.company_data['company'].id,
        })
        case.action_create_quotation()
        ro = case.action_create_repair_order()
        self.assertEqual(ro.gara_case_id, case)
        ro.action_validate()
        ro.action_repair_start()
        ro.action_repair_end()
        self.assertEqual(ro.state, 'done')
        self.assertEqual(case.state, 'done')

    def test_care_activity_and_warranty(self):
        vehicle = self._create_vehicle()
        case = self.env['gara.workshop.case'].create({
            'partner_id': self.partner_a.id,
            'vehicle_id': vehicle.id,
            'company_id': self.company_data['company'].id,
        })
        act = self.env['gara.care.activity'].create({
            'name': 'Follow-up',
            'partner_id': self.partner_a.id,
            'case_id': case.id,
            'channel': 'zalo',
        })
        self.assertEqual(act.case_id, case)
        cl = self.env['gara.warranty.claim'].create({
            'case_id': case.id,
            'vehicle_id': vehicle.id,
            'description': 'Noise after repair',
            'company_id': self.company_data['company'].id,
        })
        self.assertRegex(cl.name, r'^WCL/')

    def test_close_blocked_with_open_invoice_residual(self):
        vehicle = self._create_vehicle()
        case = self.env['gara.workshop.case'].create({
            'partner_id': self.partner_a.id,
            'vehicle_id': vehicle.id,
            'company_id': self.company_data['company'].id,
        })
        case.action_create_quotation()
        case.action_confirm_sale()
        inv = case.action_create_invoice()
        self.assertTrue(inv)
        with self.assertRaises(UserError):
            case.action_close()

    def test_insurance_reminder_and_survey(self):
        vehicle = self._create_vehicle()
        case = self.env['gara.workshop.case'].create({
            'partner_id': self.partner_a.id,
            'vehicle_id': vehicle.id,
            'company_id': self.company_data['company'].id,
        })
        claim = self.env['gara.insurance.claim'].create({
            'case_id': case.id,
            'partner_id': self.partner_a.id,
            'vehicle_id': vehicle.id,
            'approved_amount': 1000.0,
            'paid_amount': 400.0,
        })
        self.assertRegex(claim.name, r'^ICL/')
        reminder = self.env['gara.reminder'].create({
            'name': 'Insurance renewal',
            'partner_id': self.partner_a.id,
            'vehicle_id': vehicle.id,
            'case_id': case.id,
            'reminder_type': 'insurance',
            'due_date': '2026-01-01',
            'channel': 'zalo',
        })
        self.assertEqual(reminder.case_id, case)
        template = self.env['gara.survey.template'].create({
            'name': 'After service',
        })
        q1 = self.env['gara.survey.question'].create({
            'template_id': template.id,
            'text': 'Service quality',
        })
        q2 = self.env['gara.survey.question'].create({
            'template_id': template.id,
            'text': 'Price fairness',
        })
        response = self.env['gara.survey.response'].create({
            'name': 'Survey #1',
            'partner_id': self.partner_a.id,
            'case_id': case.id,
            'template_id': template.id,
            'line_ids': [
                (0, 0, {'question_id': q1.id, 'score': 4}),
                (0, 0, {'question_id': q2.id, 'score': 5}),
            ],
        })
        self.assertAlmostEqual(response.score_avg, 4.5)

    def test_survey_question_groups(self):
        template = self.env['gara.survey.template'].create({'name': 'After service grouped'})
        other_template = self.env['gara.survey.template'].create({'name': 'Other template'})
        group = self.env['gara.survey.question.group'].create({
            'template_id': template.id,
            'name': 'Service quality',
        })
        other_group = self.env['gara.survey.question.group'].create({
            'template_id': other_template.id,
            'name': 'Other group',
        })
        question = self.env['gara.survey.question'].create({
            'template_id': template.id,
            'group_id': group.id,
            'text': 'Was the advisor clear?',
        })

        self.assertEqual(question.group_id, group)
        self.assertEqual(group.question_ids, question)

        with self.assertRaises(ValidationError):
            question.write({'group_id': other_group.id})

    def test_approval_and_audit_log(self):
        vehicle = self._create_vehicle()
        case = self.env['gara.workshop.case'].create({
            'partner_id': self.partner_a.id,
            'vehicle_id': vehicle.id,
            'company_id': self.company_data['company'].id,
        })
        case.action_set_intake()
        req = case.action_request_close_approval()
        self.assertEqual(req.state, 'submitted')
        req.with_user(req.approver_id).action_approve()
        self.assertEqual(case.state, 'closed')
        log = self.env['gara.audit.log'].search([('case_id', '=', case.id), ('action', '=', 'set_intake')], limit=1)
        self.assertTrue(log)

    def test_assignment_and_notification_center(self):
        vehicle = self._create_vehicle()
        case = self.env['gara.workshop.case'].create({
            'partner_id': self.partner_a.id,
            'vehicle_id': vehicle.id,
            'company_id': self.company_data['company'].id,
        })
        assignment = self.env['gara.work.assignment'].create({
            'name': 'Check brake noise',
            'case_id': case.id,
            'assigned_to_id': self.env.user.id,
        })
        assignment.action_assign()
        self.assertEqual(assignment.state, 'assigned')

        self.env['gara.notification'].action_generate_notifications()
        notification = self.env['gara.notification'].search([
            ('model', '=', 'gara.work.assignment'),
            ('res_id', '=', assignment.id),
            ('notification_type', '=', 'assignment'),
        ], limit=1)
        self.assertTrue(notification)
        notification.action_done()
        self.assertEqual(notification.state, 'done')

    def test_csv_payment_import_wizard(self):
        vehicle = self._create_vehicle()
        case = self.env['gara.workshop.case'].create({
            'partner_id': self.partner_a.id,
            'vehicle_id': vehicle.id,
            'company_id': self.company_data['company'].id,
        })
        csv_payload = "case_ref,amount,payment_date,note\n%s,123.45,2026-01-02,Imported row\n" % case.name
        wiz = self.env['gara.payment.import.wizard'].create({
            'file_name': 'payments.csv',
            'file_data': base64.b64encode(csv_payload.encode('utf-8')),
        })
        wiz.action_import()
        payment = self.env['gara.workshop.payment'].search([('case_id', '=', case.id), ('amount', '=', 123.45)], limit=1)
        self.assertTrue(payment)

    def test_xlsx_payment_import_wizard(self):
        vehicle = self._create_vehicle()
        case = self.env['gara.workshop.case'].create({
            'partner_id': self.partner_a.id,
            'vehicle_id': vehicle.id,
            'company_id': self.company_data['company'].id,
        })
        shared_strings = [
            'case_ref', 'amount', 'payment_date', 'note',
            case.name, '2026-01-03', 'Imported xlsx'
        ]
        shared_xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="7" uniqueCount="7">'
            + ''.join(f'<si><t>{s}</t></si>' for s in shared_strings) +
            '</sst>'
        )
        sheet_xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
            '<row r="1"><c t="s"><v>0</v></c><c t="s"><v>1</v></c><c t="s"><v>2</v></c><c t="s"><v>3</v></c></row>'
            '<row r="2"><c t="s"><v>4</v></c><c><v>456.78</v></c><c t="s"><v>5</v></c><c t="s"><v>6</v></c></row>'
            '</sheetData></worksheet>'
        )
        memory = io.BytesIO()
        with zipfile.ZipFile(memory, 'w') as zf:
            zf.writestr('xl/sharedStrings.xml', shared_xml)
            zf.writestr('xl/worksheets/sheet1.xml', sheet_xml)
        wiz = self.env['gara.payment.import.wizard'].create({
            'file_name': 'payments.xlsx',
            'file_data': base64.b64encode(memory.getvalue()),
        })
        wiz.action_import()
        payment = self.env['gara.workshop.payment'].search([('case_id', '=', case.id), ('amount', '=', 456.78)], limit=1)
        self.assertTrue(payment)

    def test_threshold_requires_close_approval(self):
        self.env.company.gara_close_approval_threshold = 10.0
        vehicle = self._create_vehicle()
        case = self.env['gara.workshop.case'].create({
            'partner_id': self.partner_a.id,
            'vehicle_id': vehicle.id,
            'company_id': self.company_data['company'].id,
        })
        case.action_create_quotation()
        with self.assertRaises(UserError):
            case.action_close()

    def test_insurance_threshold_creates_approval(self):
        self.env.company.gara_insurance_approval_threshold = 100.0
        vehicle = self._create_vehicle()
        case = self.env['gara.workshop.case'].create({
            'partner_id': self.partner_a.id,
            'vehicle_id': vehicle.id,
            'company_id': self.company_data['company'].id,
        })
        claim = self.env['gara.insurance.claim'].create({
            'case_id': case.id,
            'partner_id': self.partner_a.id,
            'vehicle_id': vehicle.id,
            'approved_amount': 500.0,
        })
        claim.action_mark_approved()
        self.assertNotEqual(claim.state, 'approved')
        req = self.env['gara.approval.request'].search([
            ('insurance_claim_id', '=', claim.id),
            ('request_type', '=', 'insurance'),
        ], limit=1)
        self.assertTrue(req)

    def test_approval_policy_auto_assigns_approver(self):
        self.env['gara.approval.policy'].create({
            'name': 'Insurance > 200',
            'company_id': self.env.company.id,
            'request_type': 'insurance',
            'min_amount': 200.0,
            'approver_user_id': self.env.user.id,
        })
        vehicle = self._create_vehicle()
        case = self.env['gara.workshop.case'].create({
            'partner_id': self.partner_a.id,
            'vehicle_id': vehicle.id,
            'company_id': self.company_data['company'].id,
        })
        claim = self.env['gara.insurance.claim'].create({
            'case_id': case.id,
            'partner_id': self.partner_a.id,
            'vehicle_id': vehicle.id,
            'approved_amount': 500.0,
        })
        req = claim.action_request_approval()
        self.assertEqual(req.approver_id, self.env.user)
        self.assertEqual(req.state, 'submitted')

    def test_csv_alias_headers_work(self):
        vehicle = self._create_vehicle()
        case = self.env['gara.workshop.case'].create({
            'partner_id': self.partner_a.id,
            'vehicle_id': vehicle.id,
            'company_id': self.company_data['company'].id,
        })
        csv_payload = "case_no,money,paid_date,memo\n%s,88.5,2026-01-04,Alias row\n" % case.name
        wiz = self.env['gara.payment.import.wizard'].create({
            'file_name': 'payments_alias.csv',
            'file_data': base64.b64encode(csv_payload.encode('utf-8')),
        })
        wiz.action_import()
        payment = self.env['gara.workshop.payment'].search([('case_id', '=', case.id), ('amount', '=', 88.5)], limit=1)
        self.assertTrue(payment)

    def test_two_level_approval_flow(self):
        Users = self.env['res.users'].with_context(no_reset_password=True)
        approver_l1 = Users.create({
            'name': 'Approver L1',
            'login': 'approver_l1_gara',
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id, self.env.ref('gara_workshop.group_gara_workshop_user').id])],
            'company_ids': [(6, 0, self.env.company.ids)],
            'company_id': self.env.company.id,
        })
        approver_l2 = Users.create({
            'name': 'Approver L2',
            'login': 'approver_l2_gara',
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id, self.env.ref('gara_workshop.group_gara_workshop_user').id])],
            'company_ids': [(6, 0, self.env.company.ids)],
            'company_id': self.env.company.id,
        })
        self.env['gara.approval.policy'].create({
            'name': 'Case close > 100',
            'company_id': self.env.company.id,
            'request_type': 'case_close',
            'min_amount': 100.0,
            'approver_user_id': approver_l1.id,
            'second_approver_user_id': approver_l2.id,
        })
        req = self.env['gara.approval.request'].create({
            'request_type': 'case_close',
            'company_id': self.env.company.id,
            'amount_total': 500.0,
            'reason': 'Two-level test',
        })
        req.action_submit()
        self.assertEqual(req.approver_id, approver_l1)
        req.with_user(approver_l1).action_approve()
        self.assertEqual(req.approval_progress, '2 / 2')
        self.assertEqual(req.approver_id, approver_l2)
        self.assertEqual(req.state, 'submitted')
        req.with_user(approver_l2).action_approve()
        self.assertEqual(req.state, 'approved')

    def test_three_level_approval_policy_lines(self):
        Users = self.env['res.users'].with_context(no_reset_password=True)
        u1 = Users.create({
            'name': 'Approver T1',
            'login': 'approver_t1_gara',
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id, self.env.ref('gara_workshop.group_gara_workshop_user').id])],
            'company_ids': [(6, 0, self.env.company.ids)],
            'company_id': self.env.company.id,
        })
        u2 = Users.create({
            'name': 'Approver T2',
            'login': 'approver_t2_gara',
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id, self.env.ref('gara_workshop.group_gara_workshop_user').id])],
            'company_ids': [(6, 0, self.env.company.ids)],
            'company_id': self.env.company.id,
        })
        u3 = Users.create({
            'name': 'Approver T3',
            'login': 'approver_t3_gara',
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id, self.env.ref('gara_workshop.group_gara_workshop_user').id])],
            'company_ids': [(6, 0, self.env.company.ids)],
            'company_id': self.env.company.id,
        })
        self.env['gara.approval.policy'].create({
            'name': 'Case close chain3',
            'company_id': self.env.company.id,
            'request_type': 'case_close',
            'min_amount': 0.0,
            'line_ids': [
                (0, 0, {'sequence': 10, 'approver_user_id': u1.id}),
                (0, 0, {'sequence': 20, 'approver_user_id': u2.id}),
                (0, 0, {'sequence': 30, 'approver_user_id': u3.id}),
            ],
        })
        req = self.env['gara.approval.request'].create({
            'request_type': 'case_close',
            'company_id': self.env.company.id,
            'amount_total': 50.0,
            'reason': 'Three-level test',
        })
        req.action_submit()
        self.assertEqual(len(req.step_ids), 3)
        req.with_user(u1).action_approve()
        self.assertEqual(req.approver_id, u2)
        req.with_user(u2).action_approve()
        self.assertEqual(req.approver_id, u3)
        req.with_user(u3).action_approve()
        self.assertEqual(req.state, 'approved')

    def test_payment_import_creates_account_payment(self):
        vehicle = self._create_vehicle()
        case = self.env['gara.workshop.case'].create({
            'partner_id': self.partner_a.id,
            'vehicle_id': vehicle.id,
            'company_id': self.company_data['company'].id,
        })
        journal = self.company_data['default_journal_bank']
        csv_payload = "case_ref,amount,payment_date,note\n%s,99.0,2026-02-01,Acct import\n" % case.name
        wiz = self.env['gara.payment.import.wizard'].create({
            'company_id': self.company_data['company'].id,
            'create_account_payment': True,
            'payment_journal_id': journal.id,
            'file_name': 'payments_acct.csv',
            'file_data': base64.b64encode(csv_payload.encode('utf-8')),
        })
        wiz.action_import()
        line = self.env['gara.workshop.payment'].search([('case_id', '=', case.id), ('amount', '=', 99.0)], limit=1)
        self.assertTrue(line.account_payment_id)
        self.assertEqual(line.account_payment_id.state, 'posted')
        self.assertEqual(line.account_payment_id.gara_case_id, case)
        self.assertEqual(line.account_payment_id.amount, 99.0)

    def test_dashboard_transient_loads(self):
        dash = self.env['gara.workshop.dashboard'].create({
            'company_id': self.company_data['company'].id,
        })
        self.assertGreaterEqual(dash.stat_cases_open, 0)
        act = dash.action_open_cases_open()
        self.assertEqual(act['res_model'], 'gara.workshop.case')

    def test_gara_vn_product_defaults_skips_non_vn_company(self):
        self.env.company.gara_apply_vn_product_account_defaults()

    def test_gara_vn_product_defaults_with_vn_chart(self):
        company = self.env['res.company'].create({
            'name': 'VN Gara Co',
            'country_id': self.env.ref('base.vn').id,
        })
        self.env.user.company_ids |= company
        self.env['account.chart.template'].try_loading('vn', company=company, install_demo=False)
        company.invalidate_recordset()
        company.gara_apply_vn_product_account_defaults()
        labour = self.env.ref('gara_workshop.product_gara_labour')
        income = labour.with_company(company).product_tmpl_id.property_account_income_id
        self.assertTrue(income)
        self.assertEqual(income.code, '5113')

    def test_xlsx_sheet_label_selection(self):
        vehicle = self._create_vehicle()
        case = self.env['gara.workshop.case'].create({
            'partner_id': self.partner_a.id,
            'vehicle_id': vehicle.id,
            'company_id': self.company_data['company'].id,
        })
        shared_strings = ['case_ref', 'amount', case.name]
        shared_xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="3" uniqueCount="3">'
            + ''.join(f'<si><t>{s}</t></si>' for s in shared_strings) + '</sst>'
        )
        workbook_xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="Payments" sheetId="1" r:id="rId1"/></sheets></workbook>'
        )
        workbook_rels_xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet9.xml"/>'
            '</Relationships>'
        )
        sheet_xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
            '<row r="1"><c t="s"><v>0</v></c><c t="s"><v>1</v></c></row>'
            '<row r="2"><c t="s"><v>2</v></c><c><v>77.7</v></c></row>'
            '</sheetData></worksheet>'
        )
        memory = io.BytesIO()
        with zipfile.ZipFile(memory, 'w') as zf:
            zf.writestr('xl/sharedStrings.xml', shared_xml)
            zf.writestr('xl/workbook.xml', workbook_xml)
            zf.writestr('xl/_rels/workbook.xml.rels', workbook_rels_xml)
            zf.writestr('xl/worksheets/sheet9.xml', sheet_xml)
        wiz = self.env['gara.payment.import.wizard'].create({
            'file_name': 'sheet_by_label.xlsx',
            'xlsx_sheet_label': 'Payments',
            'file_data': base64.b64encode(memory.getvalue()),
        })
        wiz.action_import()
        payment = self.env['gara.workshop.payment'].search([('case_id', '=', case.id), ('amount', '=', 77.7)], limit=1)
        self.assertTrue(payment)

    def test_quote_workflow_logs_audit(self):
        vehicle = self._create_vehicle()
        case = self.env['gara.workshop.case'].create({
            'partner_id': self.partner_a.id,
            'vehicle_id': vehicle.id,
            'company_id': self.company_data['company'].id,
        })
        so = case.action_create_quotation()
        so.action_gara_submit_quote()
        self.assertEqual(so.gara_quote_state, 'submitted')
        so.action_gara_approve_quote()
        self.assertEqual(so.gara_quote_state, 'approved')

        submit_log = self.env['gara.audit.log'].search([
            ('case_id', '=', case.id),
            ('action', '=', 'quote_submitted'),
            ('model_name', '=', 'sale.order'),
            ('res_id', '=', so.id),
        ], limit=1)
        approve_log = self.env['gara.audit.log'].search([
            ('case_id', '=', case.id),
            ('action', '=', 'quote_approved'),
            ('model_name', '=', 'sale.order'),
            ('res_id', '=', so.id),
        ], limit=1)
        self.assertTrue(submit_log)
        self.assertTrue(approve_log)

    def test_cross_model_crud_audit_trail(self):
        vehicle = self._create_vehicle()
        case = self.env['gara.workshop.case'].create({
            'partner_id': self.partner_a.id,
            'vehicle_id': vehicle.id,
            'company_id': self.company_data['company'].id,
        })
        so = case.action_create_quotation()
        so.write({'client_order_ref': 'AUD-SO-REF'})

        journal = self.env['account.journal'].search([
            ('company_id', '=', case.company_id.id),
            ('type', '=', 'general'),
        ], limit=1)
        move = self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': journal.id,
            'date': '2026-04-23',
            'gara_case_id': case.id,
        })
        move.write({'ref': 'AUD-MOVE-REF'})
        move_id = move.id
        move.unlink()

        payment = self.env['gara.workshop.payment'].create({
            'case_id': case.id,
            'partner_id': self.partner_a.id,
            'amount': 123.0,
        })
        payment.write({'note': 'Audit update'})
        payment_id = payment.id
        payment.unlink()

        Audit = self.env['gara.audit.log']
        so_write_log = Audit.search([
            ('model_name', '=', 'sale.order'),
            ('res_id', '=', so.id),
            ('case_id', '=', case.id),
            ('action', '=', 'record_updated'),
        ], limit=1)
        move_create_log = Audit.search([
            ('model_name', '=', 'account.move'),
            ('res_id', '=', move_id),
            ('case_id', '=', case.id),
            ('action', '=', 'record_created'),
        ], limit=1)
        move_delete_log = Audit.search([
            ('model_name', '=', 'account.move'),
            ('res_id', '=', move_id),
            ('case_id', '=', case.id),
            ('action', '=', 'record_deleted'),
        ], limit=1)
        payment_create_log = Audit.search([
            ('model_name', '=', 'gara.workshop.payment'),
            ('res_id', '=', payment_id),
            ('case_id', '=', case.id),
            ('action', '=', 'record_created'),
        ], limit=1)
        payment_delete_log = Audit.search([
            ('model_name', '=', 'gara.workshop.payment'),
            ('res_id', '=', payment_id),
            ('case_id', '=', case.id),
            ('action', '=', 'record_deleted'),
        ], limit=1)

        self.assertTrue(so_write_log)
        self.assertIn('client_order_ref', so_write_log.detail)
        self.assertTrue(move_create_log)
        self.assertTrue(move_delete_log)
        self.assertTrue(payment_create_log)
        self.assertTrue(payment_delete_log)

    def test_quote_requires_approval_when_setting_enabled(self):
        self.env.company.gara_quote_require_approval = True
        vehicle = self._create_vehicle()
        case = self.env['gara.workshop.case'].create({
            'partner_id': self.partner_a.id,
            'vehicle_id': vehicle.id,
            'company_id': self.company_data['company'].id,
        })
        so = case.action_create_quotation()
        with self.assertRaises(UserError):
            case.action_confirm_sale()
        so.action_gara_submit_quote()
        so.action_gara_approve_quote()
        case.action_confirm_sale()
        self.assertEqual(case.state, 'repair')
        self.assertTrue(so.gara_quote_approval_request_id)
        self.assertEqual(so.gara_quote_approval_request_id.request_type, 'quote')
        self.assertEqual(so.gara_quote_approval_request_id.sale_order_id, so)

    def test_quote_policy_multistep_approval_flow(self):
        Users = self.env['res.users'].with_context(no_reset_password=True)
        approver_l1 = Users.create({
            'name': 'Quote Approver L1',
            'login': 'quote_approver_l1_gara',
            'groups_id': [(6, 0, [
                self.env.ref('base.group_user').id,
                self.env.ref('gara_workshop.group_gara_workshop_user').id,
                self.env.ref('sales_team.group_sale_salesman').id,
            ])],
            'company_ids': [(6, 0, self.env.company.ids)],
            'company_id': self.env.company.id,
        })
        approver_l2 = Users.create({
            'name': 'Quote Approver L2',
            'login': 'quote_approver_l2_gara',
            'groups_id': [(6, 0, [
                self.env.ref('base.group_user').id,
                self.env.ref('gara_workshop.group_gara_workshop_user').id,
                self.env.ref('sales_team.group_sale_salesman').id,
            ])],
            'company_ids': [(6, 0, self.env.company.ids)],
            'company_id': self.env.company.id,
        })
        self.env['gara.approval.policy'].create({
            'name': 'Quote chain 2 levels',
            'company_id': self.env.company.id,
            'request_type': 'quote',
            'min_amount': 0.0,
            'line_ids': [
                (0, 0, {'sequence': 10, 'approver_user_id': approver_l1.id}),
                (0, 0, {'sequence': 20, 'approver_user_id': approver_l2.id}),
            ],
        })

        vehicle = self._create_vehicle()
        case = self.env['gara.workshop.case'].create({
            'partner_id': self.partner_a.id,
            'vehicle_id': vehicle.id,
            'company_id': self.company_data['company'].id,
        })
        so = case.action_create_quotation()
        so.action_gara_submit_quote()
        req = so.gara_quote_approval_request_id

        self.assertTrue(req)
        self.assertEqual(req.request_type, 'quote')
        self.assertEqual(req.state, 'submitted')
        self.assertEqual(req.approver_id, approver_l1)
        with self.assertRaises(UserError):
            case.action_confirm_sale()

        req.with_user(approver_l1).action_approve()
        req.invalidate_recordset()
        so.invalidate_recordset()
        self.assertEqual(req.state, 'submitted')
        self.assertEqual(req.approver_id, approver_l2)
        self.assertEqual(so.gara_quote_state, 'submitted')

        req.with_user(approver_l2).action_approve()
        req.invalidate_recordset()
        so.invalidate_recordset()
        self.assertEqual(req.state, 'approved')
        self.assertEqual(so.gara_quote_state, 'approved')

    def test_quote_reject_syncs_to_approval_request(self):
        self.env['gara.approval.policy'].create({
            'name': 'Quote reject policy',
            'company_id': self.env.company.id,
            'request_type': 'quote',
            'min_amount': 0.0,
            'approver_user_id': self.env.user.id,
        })
        vehicle = self._create_vehicle()
        case = self.env['gara.workshop.case'].create({
            'partner_id': self.partner_a.id,
            'vehicle_id': vehicle.id,
            'company_id': self.company_data['company'].id,
        })
        so = case.action_create_quotation()
        so.action_gara_submit_quote()
        so.gara_quote_reject_reason = 'Need revise discount and parts'
        so.action_gara_reject_quote()

        req = so.gara_quote_approval_request_id
        self.assertEqual(req.state, 'rejected')
        self.assertEqual(so.gara_quote_state, 'rejected')
        self.assertEqual(so.gara_quote_reject_reason, 'Need revise discount and parts')

    def test_member_ledger_created_from_payment_when_membership_enabled(self):
        partner_model = self.env['res.partner']
        if 'gara_membership_type_id' not in partner_model._fields:
            self.env['gara.member.ledger'].create({
                'partner_id': self.partner_a.id,
                'entry_type': 'adjust',
                'points': 1.0,
                'state': 'posted',
            })
            return

        membership_type = self.env['gara.membership.type'].search([('code', '=', 'VIP')], limit=1)
        if not membership_type:
            membership_type = self.env['gara.membership.type'].create({
                'name': 'VIP',
                'code': 'VIP_TEST',
                'discount_percent': 5.0,
            })
        self.partner_a.gara_membership_type_id = membership_type
        self.env.company.gara_member_point_rate = 0.01
        vehicle = self._create_vehicle()
        case = self.env['gara.workshop.case'].create({
            'partner_id': self.partner_a.id,
            'vehicle_id': vehicle.id,
            'company_id': self.company_data['company'].id,
        })
        payment = self.env['gara.workshop.payment'].create({
            'case_id': case.id,
            'partner_id': self.partner_a.id,
            'amount': 1000.0,
        })

        self.assertTrue(payment.member_ledger_id)
        self.assertEqual(payment.member_ledger_id.points, 10.0)
        self.assertEqual(payment.member_ledger_id.partner_id, self.partner_a)
