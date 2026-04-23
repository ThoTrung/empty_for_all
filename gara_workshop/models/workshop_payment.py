# -*- coding: utf-8 -*-

from odoo import api, fields, models


class GaraWorkshopPayment(models.Model):
    _name = 'gara.workshop.payment'
    _description = 'Gara customer payment record (deposit / on-account)'
    _order = 'payment_date desc, id desc'

    case_id = fields.Many2one(
        'gara.workshop.case',
        string='Case',
        required=True,
        ondelete='cascade',
        index=True,
    )
    company_id = fields.Many2one(
        related='case_id.company_id',
        store=True,
        readonly=True,
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Customer',
        required=True,
    )
    amount = fields.Monetary(
        string='Amount',
        required=True,
        currency_field='currency_id',
    )
    currency_id = fields.Many2one(
        related='case_id.currency_id',
        store=True,
        readonly=True,
    )
    payment_date = fields.Date(
        string='Payment date',
        default=fields.Date.context_today,
        required=True,
    )
    note = fields.Char(string='Memo')
    account_payment_id = fields.Many2one(
        'account.payment',
        string='Accounting payment',
        readonly=True,
        ondelete='set null',
        help='Posted customer payment in Accounting when created from import or linked manually.',
    )
    member_ledger_id = fields.Many2one(
        'gara.member.ledger',
        string='Member Ledger',
        readonly=True,
        ondelete='set null',
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('case_id') and not vals.get('partner_id'):
                case = self.env['gara.workshop.case'].browse(vals['case_id'])
                vals['partner_id'] = case.partner_id.id
        records = super().create(vals_list)
        records._create_member_ledger_entries()
        for payment in records.filtered('case_id'):
            payment._gara_log_case_event(
                'record_created',
                'Created workshop payment %.2f' % payment.amount,
            )
        return records

    def _create_member_ledger_entries(self):
        partner_model = self.env['res.partner']
        has_membership_field = 'gara_membership_type_id' in partner_model._fields
        for payment in self.filtered(lambda rec: not rec.member_ledger_id and rec.amount > 0):
            partner = payment.partner_id
            if not has_membership_field or not partner.gara_membership_type_id:
                continue
            rate = payment.company_id.gara_member_point_rate or 0.0
            if rate <= 0.0:
                continue
            points = round(payment.amount * rate, 2)
            if points <= 0.0:
                continue
            ledger = self.env['gara.member.ledger'].create({
                'company_id': payment.company_id.id,
                'partner_id': partner.id,
                'case_id': payment.case_id.id,
                'payment_id': payment.id,
                'entry_date': fields.Datetime.now(),
                'entry_type': 'earn',
                'points': points,
                'amount_base': payment.amount,
                'membership_name': partner.gara_membership_type_id.display_name,
                'note': 'Auto earn from service payment',
                'state': 'posted',
            })
            payment.member_ledger_id = ledger.id
            if payment.case_id:
                payment.case_id._log_audit(
                    'member_point_earn',
                    'Earned %.2f points from payment %.2f' % (points, payment.amount),
                )

    def _gara_log_case_event(self, action, detail):
        self.ensure_one()
        if not self.case_id:
            return False
        return self.env['gara.audit.log'].log_event(
            action=action,
            model_name=self._name,
            res_id=self.id,
            company_id=self.company_id.id,
            case_id=self.case_id.id,
            detail=detail,
            event_type='user',
        )

    def write(self, vals):
        tracked_fields = sorted(set(vals) - {'write_date', 'write_uid'})
        res = super().write(vals)
        if tracked_fields:
            for payment in self.filtered('case_id'):
                payment._gara_log_case_event(
                    'record_updated',
                    'Updated fields: %s' % ', '.join(tracked_fields),
                )
        return res

    def unlink(self):
        payload = []
        for payment in self.filtered('case_id'):
            payload.append({
                'company_id': payment.company_id.id,
                'case_id': payment.case_id.id,
                'res_id': payment.id,
                'amount': payment.amount,
            })
        res = super().unlink()
        Audit = self.env['gara.audit.log']
        for vals in payload:
            Audit.log_event(
                action='record_deleted',
                model_name='gara.workshop.payment',
                res_id=vals['res_id'],
                company_id=vals['company_id'],
                case_id=vals['case_id'],
                detail='Deleted workshop payment %.2f' % vals['amount'],
                event_type='user',
            )
        return res
