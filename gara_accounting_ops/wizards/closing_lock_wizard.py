# -*- coding: utf-8 -*-

from odoo import fields, models, _
from odoo.exceptions import UserError


class GaraClosingLockWizard(models.TransientModel):
    _name = 'gara.closing.lock.wizard'
    _description = 'KGara-style accounting lock wizard'

    company_id = fields.Many2one(
        'res.company',
        required=True,
        default=lambda self: self.env.company,
    )
    period_lock_date = fields.Date(string='Journal Entries Lock Date')
    fiscalyear_lock_date = fields.Date(string='Fiscal Year Lock Date')
    tax_lock_date = fields.Date(string='Tax Lock Date')
    allow_backward = fields.Boolean(
        string='Allow moving lock dates backwards',
        help='Use only when correcting a wrong lock date. Normal closing should only move dates forward.',
    )
    note = fields.Text()

    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        company = self.env.company
        values.setdefault('company_id', company.id)
        values.setdefault('period_lock_date', company.period_lock_date)
        values.setdefault('fiscalyear_lock_date', company.fiscalyear_lock_date)
        values.setdefault('tax_lock_date', company.tax_lock_date)
        return values

    def _check_not_backward(self, field_name, new_date):
        old_date = self.company_id[field_name]
        if old_date and new_date and new_date < old_date and not self.allow_backward:
            raise UserError(_(
                'Cannot move %(field)s backwards from %(old)s to %(new)s without explicit approval.',
                field=self._fields[field_name].string,
                old=old_date,
                new=new_date,
            ))

    def action_apply(self):
        self.ensure_one()
        self._check_not_backward('period_lock_date', self.period_lock_date)
        self._check_not_backward('fiscalyear_lock_date', self.fiscalyear_lock_date)
        self._check_not_backward('tax_lock_date', self.tax_lock_date)
        values = {
            'period_lock_date': self.period_lock_date,
            'fiscalyear_lock_date': self.fiscalyear_lock_date,
            'tax_lock_date': self.tax_lock_date,
        }
        self.company_id.write(values)
        message = _(
            'KGara-style closing lock applied. Period: %(period)s; Fiscal year: %(fiscal)s; Tax: %(tax)s. %(note)s',
            period=self.period_lock_date or '-',
            fiscal=self.fiscalyear_lock_date or '-',
            tax=self.tax_lock_date or '-',
            note=self.note or '',
        )
        self.company_id.message_post(body=message)
        return {'type': 'ir.actions.act_window_close'}
