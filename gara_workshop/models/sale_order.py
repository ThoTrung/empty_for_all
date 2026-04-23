# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    gara_case_id = fields.Many2one(
        'gara.workshop.case',
        string='Gara case',
        copy=False,
        index=True,
        check_company=True,
    )
    gara_quote_state = fields.Selection(
        [('draft', 'Draft'), ('submitted', 'Submitted'), ('approved', 'Approved'), ('rejected', 'Rejected')],
        string='Gara Quote State',
        default='draft',
        copy=False,
        tracking=True,
    )
    gara_quote_submitted_by_id = fields.Many2one('res.users', string='Submitted By', readonly=True, copy=False)
    gara_quote_submitted_date = fields.Datetime(string='Submitted On', readonly=True, copy=False)
    gara_quote_approved_by_id = fields.Many2one('res.users', string='Approved By', readonly=True, copy=False)
    gara_quote_approved_date = fields.Datetime(string='Approved On', readonly=True, copy=False)
    gara_quote_reject_reason = fields.Char(string='Reject Reason', copy=False)
    gara_quote_approval_request_id = fields.Many2one(
        'gara.approval.request',
        string='Quote Approval Request',
        copy=False,
        readonly=True,
        ondelete='set null',
    )

    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)
        for order in orders.filtered('gara_case_id'):
            order._gara_log_case_event(
                'record_created',
                'Created quotation/order %s' % (order.name or order.id),
            )
        return orders

    def _prepare_invoice(self):
        vals = super()._prepare_invoice()
        if self.gara_case_id:
            vals['gara_case_id'] = self.gara_case_id.id
        return vals

    def _gara_find_quote_approval_policy(self):
        self.ensure_one()
        return self.env['gara.approval.policy'].search([
            ('active', '=', True),
            ('company_id', '=', self.company_id.id),
            ('request_type', '=', 'quote'),
            ('min_amount', '<=', self.amount_total or 0.0),
            '|',
            ('max_amount', '=', False),
            ('max_amount', '>=', self.amount_total or 0.0),
        ], limit=1)

    def _gara_quote_requires_approval(self):
        self.ensure_one()
        return bool(self.company_id.gara_quote_require_approval or self._gara_find_quote_approval_policy())

    def _gara_get_active_quote_approval_request(self):
        self.ensure_one()
        requests = self.env['gara.approval.request'].search([
            ('sale_order_id', '=', self.id),
            ('request_type', '=', 'quote'),
            ('state', 'in', ('draft', 'submitted')),
        ], order='id desc', limit=1)
        return requests

    def _gara_prepare_quote_approval_request(self):
        self.ensure_one()
        req = self._gara_get_active_quote_approval_request()
        if req:
            if req.state == 'draft':
                req.action_submit()
            return req
        policy = self._gara_find_quote_approval_policy()
        req_vals = {
            'request_type': 'quote',
            'company_id': self.company_id.id,
            'requester_id': self.env.user.id,
            'case_id': self.gara_case_id.id,
            'sale_order_id': self.id,
            'amount_total': self.amount_total,
            'reason': 'Quotation approval for %s' % (self.name or self.id),
        }
        if not policy:
            manager_group = self.env.ref('gara_workshop.group_gara_role_manager')
            if manager_group in self.env.user.groups_id:
                req_vals['approver_id'] = self.env.user.id
        request = self.env['gara.approval.request'].create(req_vals)
        request.action_submit()
        return request

    def _gara_mark_quote_approved(self, approved_by=False):
        self.ensure_one()
        approver = approved_by or self.env.user
        self.sudo().write({
            'gara_quote_state': 'approved',
            'gara_quote_approved_by_id': approver.id,
            'gara_quote_approved_date': fields.Datetime.now(),
            'gara_quote_reject_reason': False,
        })
        self._log_quote_audit('quote_approved', 'Quotation approved')
        return True

    def _gara_mark_quote_rejected(self, reject_reason=''):
        self.ensure_one()
        vals = {
            'gara_quote_state': 'rejected',
            'gara_quote_approved_by_id': False,
            'gara_quote_approved_date': False,
        }
        if reject_reason:
            vals['gara_quote_reject_reason'] = reject_reason
        self.sudo().write(vals)
        self._log_quote_audit(
            'quote_rejected',
            'Quotation rejected%s' % (': %s' % reject_reason if reject_reason else ''),
        )
        return True

    def action_gara_open_quote_approval_request(self):
        self.ensure_one()
        request = self.gara_quote_approval_request_id or self._gara_get_active_quote_approval_request()
        if not request:
            raise UserError('No quote approval request found for this quotation.')
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'gara.approval.request',
            'res_id': request.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_gara_submit_quote(self):
        for order in self:
            if not order.gara_case_id:
                raise UserError('Only Gara quotations can use this workflow.')
            if order.gara_quote_state not in ('draft', 'rejected'):
                raise UserError('Only draft/rejected quotations can be submitted.')
            order.write({
                'gara_quote_state': 'submitted',
                'gara_quote_submitted_by_id': self.env.user.id,
                'gara_quote_submitted_date': fields.Datetime.now(),
                'gara_quote_reject_reason': False,
            })
            if order._gara_quote_requires_approval():
                request = order._gara_prepare_quote_approval_request()
                order.sudo().write({'gara_quote_approval_request_id': request.id})
            order._log_quote_audit('quote_submitted', 'Quotation submitted for approval')

    def action_gara_approve_quote(self):
        for order in self:
            if order.gara_quote_state != 'submitted':
                raise UserError('Only submitted quotations can be approved.')
            request = order.gara_quote_approval_request_id or order._gara_get_active_quote_approval_request()
            if request and request.state == 'submitted':
                request.with_user(self.env.user).action_approve()
                order.sudo().write({'gara_quote_approval_request_id': request.id})
                if request.state != 'approved':
                    order._log_quote_audit(
                        'quote_approval_step',
                        'Approval step completed by %s (%s)' % (
                            self.env.user.display_name,
                            request.approval_progress or '-',
                        ),
                    )
                continue
            manager_group = self.env.ref('gara_workshop.group_gara_role_manager')
            if manager_group not in self.env.user.groups_id:
                raise UserError('Only Gara managers can approve quotations.')
            order._gara_mark_quote_approved(approved_by=self.env.user)

    def action_gara_reject_quote(self):
        for order in self:
            if order.gara_quote_state != 'submitted':
                raise UserError('Only submitted quotations can be rejected.')
            request = order.gara_quote_approval_request_id or order._gara_get_active_quote_approval_request()
            if request and request.state == 'submitted':
                if order.gara_quote_reject_reason:
                    request.decision_note = order.gara_quote_reject_reason
                request.with_user(self.env.user).action_reject()
                order.sudo().write({'gara_quote_approval_request_id': request.id})
                continue
            manager_group = self.env.ref('gara_workshop.group_gara_role_manager')
            if manager_group not in self.env.user.groups_id:
                raise UserError('Only Gara managers can reject quotations.')
            order._gara_mark_quote_rejected(reject_reason=order.gara_quote_reject_reason or '')

    def action_gara_reset_quote(self):
        manager_group = self.env.ref('gara_workshop.group_gara_role_manager')
        if manager_group not in self.env.user.groups_id:
            raise UserError('Only Gara managers can reset quotation workflow.')
        for order in self:
            request = order.gara_quote_approval_request_id or order._gara_get_active_quote_approval_request()
            if request and request.state in ('draft', 'submitted'):
                request.write({
                    'state': 'rejected',
                    'decision_note': 'Quotation workflow reset by manager.',
                })
            order.sudo().write({
                'gara_quote_state': 'draft',
                'gara_quote_submitted_by_id': False,
                'gara_quote_submitted_date': False,
                'gara_quote_approved_by_id': False,
                'gara_quote_approved_date': False,
                'gara_quote_reject_reason': False,
                'gara_quote_approval_request_id': False,
            })
            order._log_quote_audit('quote_reset', 'Quotation workflow reset')

    def _log_quote_audit(self, action, detail):
        for order in self.filtered('gara_case_id'):
            order._gara_log_case_event(action, detail)

    def _gara_log_case_event(self, action, detail):
        self.ensure_one()
        if not self.gara_case_id:
            return False
        return self.env['gara.audit.log'].log_event(
            action=action,
            model_name=self._name,
            res_id=self.id,
            company_id=self.company_id.id,
            case_id=self.gara_case_id.id,
            detail=detail,
            event_type='user',
        )

    def action_confirm(self):
        for order in self.filtered('gara_case_id'):
            if order._gara_quote_requires_approval() and order.gara_quote_state != 'approved':
                raise UserError('This quotation requires manager approval before confirmation.')
        result = super().action_confirm()
        for order in self.filtered('gara_case_id'):
            order._log_quote_audit('quote_confirmed', 'Quotation confirmed to service order')
        return result

    def write(self, vals):
        tracked_fields = sorted(set(vals) - {'write_date', 'write_uid'})
        res = super().write(vals)
        if tracked_fields:
            for order in self.filtered('gara_case_id'):
                order._gara_log_case_event(
                    'record_updated',
                    'Updated fields: %s' % ', '.join(tracked_fields),
                )
        return res

    def unlink(self):
        payload = []
        for order in self.filtered('gara_case_id'):
            payload.append({
                'company_id': order.company_id.id,
                'case_id': order.gara_case_id.id,
                'res_id': order.id,
                'name': order.name,
            })
        res = super().unlink()
        Audit = self.env['gara.audit.log']
        for vals in payload:
            Audit.log_event(
                action='record_deleted',
                model_name='sale.order',
                res_id=vals['res_id'],
                company_id=vals['company_id'],
                case_id=vals['case_id'],
                detail='Deleted quotation/order %s' % (vals['name'] or vals['res_id']),
                event_type='user',
            )
        return res


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    gara_case_id = fields.Many2one(related='order_id.gara_case_id', store=True, readonly=True, index=True)
    gara_quote_state = fields.Selection(related='order_id.gara_quote_state', store=True, readonly=True)
