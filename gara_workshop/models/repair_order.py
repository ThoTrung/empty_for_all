# -*- coding: utf-8 -*-

from odoo import api, fields, models


class RepairOrder(models.Model):
    _inherit = 'repair.order'

    gara_case_id = fields.Many2one(
        'gara.workshop.case',
        string='Gara case',
        copy=False,
        index=True,
        check_company=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for ro in records.filtered('gara_case_id'):
            ro._gara_log_case_event(
                'record_created',
                'Created repair order %s' % (ro.name or ro.id),
            )
        return records

    def write(self, vals):
        tracked_fields = sorted(set(vals) - {'write_date', 'write_uid'})
        res = super().write(vals)
        if tracked_fields:
            for ro in self.filtered('gara_case_id'):
                ro._gara_log_case_event(
                    'record_updated',
                    'Updated fields: %s' % ', '.join(tracked_fields),
                )
        if vals.get('state') == 'done':
            for ro in self.filtered('gara_case_id'):
                if ro.gara_case_id.state == 'repair':
                    ro.gara_case_id.state = 'done'
        if vals.get('state') == 'cancel':
            for ro in self.filtered('gara_case_id'):
                case = ro.gara_case_id
                if case.state == 'repair':
                    case.state = 'cancel'
        return res

    def unlink(self):
        payload = []
        for ro in self.filtered('gara_case_id'):
            payload.append({
                'company_id': ro.company_id.id,
                'case_id': ro.gara_case_id.id,
                'res_id': ro.id,
                'name': ro.name,
            })
        res = super().unlink()
        Audit = self.env['gara.audit.log']
        for vals in payload:
            Audit.log_event(
                action='record_deleted',
                model_name='repair.order',
                res_id=vals['res_id'],
                company_id=vals['company_id'],
                case_id=vals['case_id'],
                detail='Deleted repair order %s' % (vals['name'] or vals['res_id']),
                event_type='user',
            )
        return res

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
