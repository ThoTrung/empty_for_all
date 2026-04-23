# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class GaraWorkshopCase(models.Model):
    _name = 'gara.workshop.case'
    _description = 'Gara Workshop Case (service job / vu viec)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(
        string='Reference',
        required=True,
        copy=False,
        readonly=True,
        default='New',
        index='trigram',
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    currency_id = fields.Many2one(
        related='company_id.currency_id',
        string='Currency',
    )
    active = fields.Boolean(default=True)
    partner_id = fields.Many2one(
        'res.partner',
        string='Customer',
        required=True,
        tracking=True,
        index=True,
    )
    vehicle_id = fields.Many2one(
        'fleet.vehicle',
        string='Vehicle',
        tracking=True,
        index=True,
    )
    user_id = fields.Many2one(
        'res.users',
        string='Service Advisor',
        default=lambda self: self.env.user,
        tracking=True,
    )
    odometer_in = fields.Float(string='Odometer (in)')
    intake_date = fields.Datetime(string='Intake time', default=fields.Datetime.now)
    intake_notes = fields.Html(string='Intake / condition notes')

    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('intake', 'Intake'),
            ('quoted', 'Quoted'),
            ('repair', 'Under repair'),
            ('done', 'Repair done'),
            ('invoiced', 'Invoiced'),
            ('closed', 'Closed'),
            ('cancel', 'Cancelled'),
        ],
        string='Status',
        default='draft',
        tracking=True,
        copy=False,
        index=True,
    )

    sale_order_id = fields.Many2one(
        'sale.order',
        string='Quotation / Order',
        copy=False,
        tracking=True,
        check_company=True,
    )
    repair_order_id = fields.Many2one(
        'repair.order',
        string='Repair Order',
        copy=False,
        tracking=True,
        check_company=True,
    )
    invoice_ids = fields.One2many(
        'account.move',
        'gara_case_id',
        string='Invoices',
        domain=[('move_type', '=', 'out_invoice')],
    )
    payment_line_ids = fields.One2many(
        'gara.workshop.payment',
        'case_id',
        string='Customer payments (on account)',
    )

    amount_sale_total = fields.Monetary(
        string='SO Total',
        compute='_compute_financials',
        currency_field='currency_id',
    )
    amount_invoiced_total = fields.Monetary(
        string='Invoiced total',
        compute='_compute_financials',
        currency_field='currency_id',
    )
    amount_residual_invoices = fields.Monetary(
        string='Invoice residual',
        compute='_compute_financials',
        currency_field='currency_id',
    )
    amount_payment_registered = fields.Monetary(
        string='Payments recorded',
        compute='_compute_financials',
        currency_field='currency_id',
    )
    amount_due_estimate = fields.Monetary(
        string='Due (estimate)',
        compute='_compute_financials',
        currency_field='currency_id',
        help='If invoices exist: sum of invoice residual. Else: SO total minus recorded payments.',
    )

    care_activity_ids = fields.One2many(
        'gara.care.activity',
        'case_id',
        string='Care log',
    )
    warranty_claim_ids = fields.One2many(
        'gara.warranty.claim',
        'case_id',
        string='Warranty claims',
    )
    insurance_claim_ids = fields.One2many(
        'gara.insurance.claim',
        'case_id',
        string='Insurance claims',
    )
    reminder_ids = fields.One2many(
        'gara.reminder',
        'case_id',
        string='Reminders',
    )
    survey_response_ids = fields.One2many(
        'gara.survey.response',
        'case_id',
        string='Survey responses',
    )
    approval_request_ids = fields.One2many(
        'gara.approval.request',
        'case_id',
        string='Approval requests',
    )
    assignment_ids = fields.One2many(
        'gara.work.assignment',
        'case_id',
        string='Work assignments',
    )
    audit_log_ids = fields.One2many(
        'gara.audit.log',
        'case_id',
        string='Audit logs',
    )

    def _log_audit(self, action, detail=''):
        self.env['gara.audit.log'].log_event(
            action=action,
            model_name=self._name,
            res_id=self.id,
            company_id=self.company_id.id,
            case_id=self.id,
            detail=detail or '',
            event_type='user',
        )

    @api.constrains('vehicle_id', 'company_id')
    def _check_vehicle_company(self):
        for rec in self:
            v_company = rec.vehicle_id.company_id
            if rec.vehicle_id and v_company and v_company != rec.company_id:
                raise ValidationError(_('Vehicle belongs to another company than this case.'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('gara.workshop.case') or 'New'
        return super().create(vals_list)

    @api.depends(
        'sale_order_id.amount_total',
        'invoice_ids.amount_total',
        'invoice_ids.amount_residual',
        'invoice_ids.state',
        'payment_line_ids.amount',
    )
    def _compute_financials(self):
        for case in self:
            so = case.sale_order_id
            posted_inv = case.invoice_ids.filtered(
                lambda m: m.state == 'posted' and m.move_type == 'out_invoice'
            )
            pay_sum = sum(case.payment_line_ids.mapped('amount'))
            case.amount_sale_total = so.amount_total if so else 0.0
            case.amount_invoiced_total = sum(posted_inv.mapped('amount_total'))
            case.amount_residual_invoices = sum(posted_inv.mapped('amount_residual'))
            case.amount_payment_registered = pay_sum
            if posted_inv:
                case.amount_due_estimate = case.amount_residual_invoices
            elif so:
                case.amount_due_estimate = max(so.amount_total - pay_sum, 0.0)
            else:
                case.amount_due_estimate = 0.0

    def action_set_intake(self):
        for case in self:
            if case.state != 'draft':
                raise UserError(_('Only draft cases can move to intake.'))
            case.state = 'intake'
            case._log_audit('set_intake', f'Case moved to intake by {self.env.user.display_name}')

    def action_create_quotation(self):
        self.ensure_one()
        if self.state in ('cancel', 'closed'):
            raise UserError(_('Cancelled/closed case cannot be quoted.'))
        labour = self.env.ref('gara_workshop.product_gara_labour', raise_if_not_found=False)
        if not labour:
            raise UserError(_('Missing data product_gara_labour.'))
        if self.sale_order_id:
            raise UserError(_('A quotation already exists.'))
        so = self.env['sale.order'].create({
            'partner_id': self.partner_id.id,
            'company_id': self.company_id.id,
            'origin': self.name,
            'gara_case_id': self.id,
        })
        self.env['sale.order.line'].create({
            'order_id': so.id,
            'product_id': labour.id,
            'product_uom_qty': 1.0,
            'name': _('Labour — case %s') % self.name,
        })
        self.sale_order_id = so.id
        self.state = 'quoted'
        self._log_audit('create_quotation', f'SO {so.name} created')
        return so

    def action_confirm_sale(self):
        self.ensure_one()
        if not self.sale_order_id:
            raise UserError(_('Create a quotation first.'))
        self.sale_order_id.action_confirm()
        if self.state == 'quoted':
            self.state = 'repair'
        self._log_audit('confirm_sale', f'SO {self.sale_order_id.name} confirmed')

    def action_create_repair_order(self):
        self.ensure_one()
        subject = self.env.ref('gara_workshop.product_gara_repair_subject', raise_if_not_found=False)
        if not subject:
            raise UserError(_('Missing data product_gara_repair_subject.'))
        if self.repair_order_id:
            raise UserError(_('Repair order already linked.'))
        warehouse = self.env.user.with_company(self.company_id)._get_default_warehouse_id()
        picking_type = warehouse.repair_type_id if warehouse else False
        if not picking_type:
            picking_type = self.env['stock.picking.type'].search([
                ('company_id', '=', self.company_id.id),
                ('code', '=', 'repair_operation'),
            ], limit=1)
        if not picking_type or not picking_type.sequence_id:
            raise UserError(_(
                'No repair operation type / sequence for company %(c)s. Configure a warehouse repair operation.',
                c=self.company_id.display_name,
            ))
        ro = self.env['repair.order'].create({
            'partner_id': self.partner_id.id,
            'company_id': self.company_id.id,
            'picking_type_id': picking_type.id,
            'product_id': subject.id,
            'product_qty': 1.0,
            'gara_case_id': self.id,
            'sale_order_id': self.sale_order_id.id if self.sale_order_id else False,
        })
        self.repair_order_id = ro.id
        if self.state in ('quoted', 'intake'):
            self.state = 'repair'
        self._log_audit('create_repair_order', f'RO {ro.name} created')
        return ro

    def action_create_invoice(self):
        self.ensure_one()
        if not self.sale_order_id:
            raise UserError(_('No sale order to invoice.'))
        moves = self.sale_order_id._create_invoices()
        for move in moves:
            move.gara_case_id = self.id
        if moves:
            self.state = 'invoiced'
        self._log_audit('create_invoice', f'{len(moves)} invoice(s) created')
        return moves

    def action_register_payment_line(self, amount):
        """Used by tests and server actions; creates an on-account payment record."""
        self.ensure_one()
        if amount <= 0:
            raise UserError(_('Amount must be positive.'))
        payment = self.env['gara.workshop.payment'].create({
            'case_id': self.id,
            'partner_id': self.partner_id.id,
            'amount': amount,
        })
        self._log_audit('register_payment', f'Payment line {payment.amount} created')
        return payment

    def action_close(self):
        for case in self:
            threshold = case.company_id.gara_close_approval_threshold or 0.0
            if threshold and case.amount_sale_total > threshold:
                approved = case.approval_request_ids.filtered(
                    lambda r: r.request_type == 'case_close' and r.state == 'approved'
                )
                if not approved:
                    raise UserError(_('Close approval is required before closing this case.'))
            draft_inv = case.invoice_ids.filtered(lambda m: m.state == 'draft')
            if draft_inv:
                raise UserError(_('Cannot close: draft invoices still exist.'))
            open_inv = case.invoice_ids.filtered(
                lambda m: m.state == 'posted' and m.amount_residual > 0
            )
            if open_inv:
                raise UserError(_('Cannot close: posted invoices still have a balance due.'))
            case.state = 'closed'
            case._log_audit('close_case', 'Case closed')

    def action_cancel(self):
        for case in self:
            case.state = 'cancel'
            case._log_audit('cancel_case', 'Case cancelled')

    def action_request_close_approval(self):
        self.ensure_one()
        manager_group = self.env.ref('gara_workshop.group_gara_role_manager', raise_if_not_found=False)
        manager_user = self.env['res.users']
        if manager_group:
            manager_user = self.env['res.users'].search([('groups_id', 'in', manager_group.id)], limit=1)
        req = self.env['gara.approval.request'].create({
            'request_type': 'case_close',
            'case_id': self.id,
            'company_id': self.company_id.id,
            'reason': _('Request approval to close case %(case)s') % {'case': self.name},
            'approver_id': manager_user.id if manager_user else False,
            'amount_total': self.amount_sale_total,
        })
        req.action_submit()
        self._log_audit('request_close_approval', f'Approval request {req.name} submitted')
        return req
