# -*- coding: utf-8 -*-

from odoo import fields, models, _
from odoo.exceptions import UserError


def _field_exists(env, model_name, field_name):
    return model_name in env and field_name in env[model_name]._fields


class GaraPartnerMergeWizard(models.TransientModel):
    _name = 'gara.partner.merge.wizard'
    _description = 'KGara-style Partner Merge Wizard'

    target_partner_id = fields.Many2one('res.partner', required=True)
    source_partner_ids = fields.Many2many(
        'res.partner',
        relation='gara_partner_merge_source_rel',
        column1='wizard_id',
        column2='partner_id',
        required=True,
    )
    archive_sources = fields.Boolean(default=True)
    confirm = fields.Boolean(string='I understand this operation cannot be automatically undone')
    updated_reference_count = fields.Integer(readonly=True)

    def _reference_fields(self):
        return [
            ('gara.workshop.case', 'partner_id'),
            ('gara.workshop.payment', 'partner_id'),
            ('gara.care.activity', 'partner_id'),
            ('gara.service.reminder', 'partner_id'),
            ('gara.insurance.claim', 'partner_id'),
            ('gara.insurance.claim', 'insurer_partner_id'),
            ('gara.survey.response', 'partner_id'),
            ('gara.notification', 'partner_id'),
            ('fleet.vehicle', 'driver_id'),
            ('sale.order', 'partner_id'),
            ('sale.order', 'partner_invoice_id'),
            ('sale.order', 'partner_shipping_id'),
            ('account.move', 'partner_id'),
            ('account.move.line', 'partner_id'),
            ('account.payment', 'partner_id'),
            ('res.partner.bank', 'partner_id'),
            ('calendar.event', 'partner_ids'),
        ]

    def _merge_references(self, source_records, target_record):
        updated = 0
        source_ids = source_records.ids
        for model_name, field_name in self._reference_fields():
            if not _field_exists(self.env, model_name, field_name):
                continue
            Model = self.env[model_name]
            field = Model._fields[field_name]
            records = Model.search([(field_name, 'in', source_ids)])
            if not records:
                continue
            if field.type == 'many2many':
                records.write({field_name: [(3, source.id) for source in source_records] + [(4, target_record.id)]})
            else:
                records.write({field_name: target_record.id})
            updated += len(records)
        return updated

    def action_merge(self):
        self.ensure_one()
        if not self.confirm:
            raise UserError(_('Please confirm before merging partners.'))
        sources = self.source_partner_ids - self.target_partner_id
        if not sources:
            raise UserError(_('Select at least one source partner different from the target partner.'))
        updated = self._merge_references(sources, self.target_partner_id)
        if self.archive_sources and 'active' in sources._fields:
            sources.write({'active': False})
        self.updated_reference_count = updated
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }


class GaraProductMergeWizard(models.TransientModel):
    _name = 'gara.product.merge.wizard'
    _description = 'KGara-style Product Merge Wizard'

    target_product_id = fields.Many2one('product.product', required=True)
    source_product_ids = fields.Many2many(
        'product.product',
        relation='gara_product_merge_source_rel',
        column1='wizard_id',
        column2='product_id',
        required=True,
    )
    archive_sources = fields.Boolean(default=True)
    confirm = fields.Boolean(string='I understand this operation cannot be automatically undone')
    updated_reference_count = fields.Integer(readonly=True)

    def _product_reference_fields(self):
        return [
            ('sale.order.line', 'product_id'),
            ('account.move.line', 'product_id'),
            ('account.payment', 'force_outstanding_account_id'),
            ('stock.move', 'product_id'),
            ('stock.move.line', 'product_id'),
            ('purchase.order.line', 'product_id'),
            ('repair.line', 'product_id'),
            ('gara.service.package.line', 'product_id'),
            ('gara.warranty.claim', 'product_id'),
            ('gara.product.norm.line', 'product_id'),
            ('gara.production.cost.line', 'product_id'),
        ]

    def _template_reference_fields(self):
        return [
            ('gara.product.norm', 'product_tmpl_id'),
        ]

    def _merge_reference_fields(self, reference_fields, source_records, target_record):
        updated = 0
        source_ids = source_records.ids
        for model_name, field_name in reference_fields:
            if not _field_exists(self.env, model_name, field_name):
                continue
            Model = self.env[model_name]
            field = Model._fields[field_name]
            if field.comodel_name != target_record._name:
                continue
            records = Model.search([(field_name, 'in', source_ids)])
            if not records:
                continue
            records.write({field_name: target_record.id})
            updated += len(records)
        return updated

    def _archive_source_products(self, sources):
        if 'active' in sources._fields:
            sources.write({'active': False})
        for template in sources.product_tmpl_id:
            source_variants = sources.filtered(lambda product: product.product_tmpl_id == template)
            if not (template.product_variant_ids - source_variants) and 'active' in template._fields:
                template.write({'active': False})

    def action_merge(self):
        self.ensure_one()
        if not self.confirm:
            raise UserError(_('Please confirm before merging products.'))
        sources = self.source_product_ids - self.target_product_id
        if not sources:
            raise UserError(_('Select at least one source product different from the target product.'))
        updated = self._merge_reference_fields(self._product_reference_fields(), sources, self.target_product_id)
        source_templates = sources.product_tmpl_id - self.target_product_id.product_tmpl_id
        if source_templates:
            updated += self._merge_reference_fields(
                self._template_reference_fields(),
                source_templates,
                self.target_product_id.product_tmpl_id,
            )
        if self.archive_sources:
            self._archive_source_products(sources)
        self.updated_reference_count = updated
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
