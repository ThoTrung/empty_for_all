# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AccountMove(models.Model):
    _inherit = 'account.move'

    gara_business_type = fields.Selection(
        selection=[
            ('service', 'Service'),
            ('parts', 'Parts'),
            ('insurance', 'Insurance'),
            ('other', 'Other'),
        ],
        string='Gara Business Type',
        default='other',
        tracking=True,
    )
    gara_payment_channel = fields.Selection(
        selection=[
            ('cash', 'Cash'),
            ('bank', 'Bank Transfer'),
            ('card', 'Card'),
            ('ewallet', 'E-Wallet'),
            ('other', 'Other'),
        ],
        string='Gara Payment Channel',
        default='other',
        tracking=True,
    )
    gara_tax_scope = fields.Selection(
        selection=[('vat', 'VAT'), ('non_vat', 'Non VAT')],
        string='Gara Tax Scope',
        compute='_compute_gara_tax_scope',
        store=True,
        readonly=True,
    )
    gara_accounting_rule_id = fields.Many2one(
        'gara.accounting.rule',
        string='Applied Gara Accounting Rule',
        copy=False,
        readonly=True,
        ondelete='set null',
    )
    gara_document_number = fields.Char(
        string='Gara Document Number',
        copy=False,
        readonly=True,
        index=True,
    )
    gara_document_group_id = fields.Many2one(
        'gara.account.document.group',
        string='Gara Document Group',
        tracking=True,
    )
    gara_document_reason_id = fields.Many2one(
        'gara.account.document.reason',
        string='Gara Document Reason',
        tracking=True,
    )
    gara_document_note = fields.Char(string='Gara Document Note')

    @api.depends('invoice_line_ids.tax_ids', 'line_ids.tax_line_id')
    def _compute_gara_tax_scope(self):
        for move in self:
            has_vat = bool(move.invoice_line_ids.filtered(lambda line: line.tax_ids))
            if not has_vat:
                has_vat = bool(move.line_ids.filtered('tax_line_id'))
            move.gara_tax_scope = 'vat' if has_vat else 'non_vat'

    @api.onchange('gara_document_group_id')
    def _onchange_gara_document_group_id(self):
        for move in self:
            if move.gara_document_group_id and move.gara_business_type == 'other':
                group_code = (move.gara_document_group_id.code or '').upper()
                if group_code in ('HDBH', 'PT'):
                    move.gara_business_type = 'service'
                elif group_code == 'HDMH':
                    move.gara_business_type = 'parts'

    @api.onchange('partner_id')
    def _onchange_partner_id_gara_business_type(self):
        for move in self:
            if not move.partner_id or move.gara_business_type != 'other':
                continue
            if move._gara_partner_scope() == 'insurance':
                move.gara_business_type = 'insurance'

    @api.model_create_multi
    def create(self, vals_list):
        moves = super().create(vals_list)
        moves._gara_apply_document_defaults()
        moves._gara_apply_accounting_rules()
        moves._gara_assign_document_number()
        return moves

    def write(self, vals):
        res = super().write(vals)
        if self.env.context.get('gara_skip_policy_apply'):
            return res
        trigger_fields = {
            'move_type',
            'partner_id',
            'invoice_line_ids',
            'line_ids',
            'journal_id',
            'company_id',
            'date',
            'gara_business_type',
            'gara_payment_channel',
            'gara_document_group_id',
            'gara_document_reason_id',
        }
        if trigger_fields.intersection(vals):
            draft_moves = self.filtered(lambda move: move.state == 'draft')
            draft_moves.with_context(gara_skip_policy_apply=True)._gara_apply_document_defaults()
            draft_moves.with_context(gara_skip_policy_apply=True)._gara_apply_accounting_rules()
            if {'date', 'company_id'}.intersection(vals):
                draft_moves.with_context(gara_skip_policy_apply=True)._gara_assign_document_number()
        return res

    @api.onchange('gara_document_group_id')
    def _onchange_gara_document_group_id_default_reason(self):
        for move in self:
            if (
                move.gara_document_reason_id
                and move.gara_document_reason_id.group_id
                and move.gara_document_reason_id.group_id != move.gara_document_group_id
            ):
                move.gara_document_reason_id = False
            if not move.gara_document_reason_id and move.gara_document_group_id.default_reason_id:
                move.gara_document_reason_id = move.gara_document_group_id.default_reason_id

    @api.constrains('gara_document_group_id', 'gara_document_reason_id')
    def _check_gara_document_reason_group(self):
        for move in self:
            reason = move.gara_document_reason_id
            group = move.gara_document_group_id
            if reason and reason.group_id and group and reason.group_id != group:
                raise ValidationError(
                    _('The document reason must belong to the selected document group.')
                )

    def _gara_partner_scope(self):
        self.ensure_one()
        partner = self.partner_id
        if partner and 'gara_customer_type_id' in partner._fields and partner.gara_customer_type_id:
            if (partner.gara_customer_type_id.code or '').upper() == 'INSURANCE':
                return 'insurance'
        if self.move_type in ('out_invoice', 'out_refund', 'out_receipt'):
            return 'customer'
        if self.move_type in ('in_invoice', 'in_refund', 'in_receipt'):
            return 'supplier'
        if partner and partner.customer_rank and not partner.supplier_rank:
            return 'customer'
        if partner and partner.supplier_rank and not partner.customer_rank:
            return 'supplier'
        return 'customer'

    def _gara_default_group_and_reason(self):
        self.ensure_one()
        company = self.company_id
        if self.move_type == 'out_receipt':
            return company.gara_default_receipt_group_id, company.gara_default_receipt_reason_id
        if self.move_type == 'in_receipt':
            return company.gara_default_payment_group_id, company.gara_default_payment_reason_id
        if self.move_type in ('out_invoice', 'out_refund'):
            return company.gara_default_sale_invoice_group_id, company.gara_default_sale_invoice_reason_id
        if self.move_type in ('in_invoice', 'in_refund'):
            return company.gara_default_purchase_invoice_group_id, company.gara_default_purchase_invoice_reason_id
        return company.gara_default_journal_group_id, company.gara_default_journal_reason_id

    def _gara_apply_document_defaults(self):
        for move in self.filtered(lambda rec: rec.state == 'draft'):
            if not move.company_id.gara_enable_document_auto_defaults:
                continue
            default_group, default_reason = move._gara_default_group_and_reason()
            vals = {}
            if default_group and not move.gara_document_group_id:
                vals['gara_document_group_id'] = default_group.id
            if default_reason and not move.gara_document_reason_id:
                vals['gara_document_reason_id'] = default_reason.id
            if not vals and move.gara_document_reason_id and not move.gara_document_group_id and move.gara_document_reason_id.group_id:
                vals['gara_document_group_id'] = move.gara_document_reason_id.group_id.id
            if vals:
                move.with_context(
                    gara_skip_policy_apply=True,
                    skip_invoice_sync=True,
                ).write(vals)
        return True

    def _gara_find_accounting_rule(self):
        self.ensure_one()
        Rule = self.env['gara.accounting.rule']
        rules = Rule.search([
            ('company_id', '=', self.company_id.id),
            ('active', '=', True),
        ], order='sequence, id')
        for rule in rules:
            if rule._match_move(self):
                return rule
        return Rule

    def _gara_apply_accounting_rules(self):
        for move in self.filtered(lambda rec: rec.state == 'draft'):
            if not move.company_id.gara_enable_accounting_rule_engine:
                continue
            move._compute_gara_tax_scope()
            rule = move._gara_find_accounting_rule()
            vals = {'gara_accounting_rule_id': rule.id or False}
            if rule:
                if rule.output_journal_id and move.journal_id != rule.output_journal_id:
                    vals['journal_id'] = rule.output_journal_id.id
                if rule.output_document_group_id and not move.gara_document_group_id:
                    vals['gara_document_group_id'] = rule.output_document_group_id.id
                if rule.output_document_reason_id and not move.gara_document_reason_id:
                    vals['gara_document_reason_id'] = rule.output_document_reason_id.id
            move.with_context(gara_skip_policy_apply=True).write(vals)

            if not rule or not move.is_invoice(include_receipts=True):
                continue
            target_account = False
            if move.move_type in ('out_invoice', 'out_refund', 'out_receipt'):
                target_account = rule.output_income_account_id
            elif move.move_type in ('in_invoice', 'in_refund', 'in_receipt'):
                target_account = rule.output_expense_account_id
            if target_account:
                lines = move.invoice_line_ids.filtered(lambda line: line.display_type == 'product')
                if lines:
                    line_commands = []
                    for line in lines:
                        if line.gara_forced_account_id != target_account or line.account_id != target_account:
                            line_commands.append((1, line.id, {
                                'gara_forced_account_id': target_account.id,
                                'account_id': target_account.id,
                            }))
                    if line_commands:
                        move.with_context(
                            check_move_validity=False,
                            gara_skip_policy_apply=True,
                            skip_invoice_sync=True,
                        ).write({'invoice_line_ids': line_commands})
                        move.invoice_line_ids._compute_account_id()
        return True

    def _gara_format_document_number(self, prefix, padding, number):
        return '%s%s' % (prefix or '', str(number).zfill(padding))

    def _gara_render_document_prefix(self):
        self.ensure_one()
        move_date = self.date or fields.Date.context_today(self)
        group_code = (self.gara_document_group_id.code or self.move_type or '').upper()
        reason_code = (self.gara_document_reason_id.code or '').upper()
        company = self.company_id
        tokens = {
            'group': group_code,
            'reason': reason_code,
            'move_type': (self.move_type or '').upper(),
            'year': str(move_date.year),
            'month': str(move_date.month).zfill(2),
            'day': str(move_date.day).zfill(2),
        }
        try:
            return (company.gara_document_number_prefix or '') % tokens
        except Exception:
            return company.gara_document_number_prefix or ''

    def _gara_next_document_number_from_company(self):
        self.ensure_one()
        company = self.company_id
        move_date = self.date or fields.Date.context_today(self)
        year = move_date.year
        if company.gara_document_number_reset_yearly and company.gara_document_number_year != year:
            company.write({
                'gara_document_number_year': year,
                'gara_document_number_next': 1,
            })
        current = company.gara_document_number_next
        company.write({'gara_document_number_next': current + 1})
        return self._gara_format_document_number(
            self._gara_render_document_prefix(),
            company.gara_document_number_padding,
            current,
        )

    def _gara_assign_document_number(self):
        SequenceRule = self.env['gara.document.sequence.rule']
        for move in self.filtered(lambda rec: rec.state == 'draft' and not rec.gara_document_number):
            company = move.company_id
            if not company.gara_enable_document_numbering:
                continue
            rules = SequenceRule.search([
                ('company_id', '=', company.id),
                ('active', '=', True),
            ], order='sequence, id')
            sequence_rule = rules.filtered(lambda rule: rule._match_move(move))[:1]
            if sequence_rule:
                document_number = sequence_rule.next_by_move(move)
            else:
                document_number = move._gara_next_document_number_from_company()
            vals = {'gara_document_number': document_number}
            if company.gara_document_number_sync_ref and not move.ref:
                vals['ref'] = document_number
            move.with_context(
                gara_skip_policy_apply=True,
                skip_invoice_sync=True,
            ).write(vals)
        return True

    def action_gara_apply_accounting_policy(self):
        self.ensure_one()
        self._gara_apply_document_defaults()
        self._gara_apply_accounting_rules()
        self._gara_assign_document_number()
        return True


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    gara_forced_account_id = fields.Many2one(
        'account.account',
        string='Gara Forced Account',
        check_company=True,
        domain="[('deprecated', '=', False), ('account_type', '!=', 'off_balance')]",
    )

    def _compute_account_id(self):
        super()._compute_account_id()
        forced_lines = self.filtered(
            lambda line: (
                line.gara_forced_account_id
                and line.display_type == 'product'
                and line.move_id.is_invoice(True)
            )
        )
        for line in forced_lines:
            line.account_id = line.gara_forced_account_id
