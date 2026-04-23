# -*- coding: utf-8 -*-

from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    gara_case_id = fields.Many2one(
        'gara.workshop.case',
        string='Gara case',
        copy=False,
        index=True,
        check_company=True,
    )

    def _reverse_moves(self, default_values_list=None, cancel=False):
        """Keep workshop case on credit notes / reversals for traceability and reporting."""
        if not default_values_list:
            default_values_list = [{} for _ in self]
        for move, defaults in zip(self, default_values_list):
            if move.gara_case_id:
                defaults.setdefault('gara_case_id', move.gara_case_id.id)
        return super()._reverse_moves(default_values_list=default_values_list, cancel=cancel)

    @api.model_create_multi
    def create(self, vals_list):
        moves = super().create(vals_list)
        for move in moves.filtered('gara_case_id'):
            move._gara_log_case_event(
                'record_created',
                'Created accounting document %s' % (move.name or move.ref or move.id),
            )
        return moves

    def write(self, vals):
        tracked_fields = sorted(set(vals) - {'write_date', 'write_uid'})
        res = super().write(vals)
        if tracked_fields:
            for move in self.filtered('gara_case_id'):
                move._gara_log_case_event(
                    'record_updated',
                    'Updated fields: %s' % ', '.join(tracked_fields),
                )
        return res

    def unlink(self):
        payload = []
        for move in self.filtered('gara_case_id'):
            payload.append({
                'company_id': move.company_id.id,
                'case_id': move.gara_case_id.id,
                'res_id': move.id,
                'name': move.name or move.ref,
            })
        res = super().unlink()
        Audit = self.env['gara.audit.log']
        for vals in payload:
            Audit.log_event(
                action='record_deleted',
                model_name='account.move',
                res_id=vals['res_id'],
                company_id=vals['company_id'],
                case_id=vals['case_id'],
                detail='Deleted accounting document %s' % (vals['name'] or vals['res_id']),
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


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    gara_case_id = fields.Many2one(
        'gara.workshop.case',
        string='Gara case',
        related='move_id.gara_case_id',
        store=True,
        readonly=True,
        index=True,
        check_company=True,
    )
