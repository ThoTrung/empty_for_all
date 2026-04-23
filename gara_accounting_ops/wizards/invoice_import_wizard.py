# -*- coding: utf-8 -*-

import base64
import csv
import io
import zipfile
import xml.etree.ElementTree as ET

from odoo import fields, models, _
from odoo.exceptions import UserError


class GaraInvoiceImportWizard(models.TransientModel):
    _name = 'gara.invoice.import.wizard'
    _description = 'Import customer/vendor invoices from CSV/XLSX'

    company_id = fields.Many2one(
        'res.company',
        required=True,
        default=lambda self: self.env.company,
    )
    move_type = fields.Selection(
        [
            ('out_invoice', 'Customer Invoice'),
            ('in_invoice', 'Vendor Bill'),
        ],
        required=True,
        default='out_invoice',
    )
    journal_id = fields.Many2one(
        'account.journal',
        domain="[('company_id', '=', company_id)]",
    )
    gara_document_group_id = fields.Many2one('gara.account.document.group')
    gara_document_reason_id = fields.Many2one(
        'gara.account.document.reason',
        domain="['|', ('group_id', '=', False), ('group_id', '=', gara_document_group_id)]",
    )
    file_data = fields.Binary(required=True)
    file_name = fields.Char()
    xlsx_sheet_name = fields.Char(
        string='XLSX sheet path',
        default='xl/worksheets/sheet1.xml',
    )
    xlsx_sheet_label = fields.Char(string='XLSX sheet name')

    def _resolve_sheet_path(self, zf):
        if self.xlsx_sheet_label:
            ns = {'x': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
            rel_ns = {'r': 'http://schemas.openxmlformats.org/package/2006/relationships'}
            workbook = ET.fromstring(zf.read('xl/workbook.xml'))
            rels = ET.fromstring(zf.read('xl/_rels/workbook.xml.rels'))
            rel_id = False
            for sheet in workbook.findall('.//x:sheets/x:sheet', ns):
                if (sheet.attrib.get('name') or '').strip() == self.xlsx_sheet_label.strip():
                    rel_id = sheet.attrib.get(
                        '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'
                    )
                    break
            if not rel_id:
                raise UserError(_('Sheet name not found: %s') % self.xlsx_sheet_label)
            target = False
            for node in rels.findall('.//r:Relationship', rel_ns):
                if node.attrib.get('Id') == rel_id:
                    target = node.attrib.get('Target')
                    break
            if not target:
                raise UserError(_('Cannot resolve sheet relation for: %s') % self.xlsx_sheet_label)
            if not target.startswith('worksheets/'):
                raise UserError(_('Unsupported sheet target path: %s') % target)
            return 'xl/' + target
        return self.xlsx_sheet_name or 'xl/worksheets/sheet1.xml'

    def _iter_rows_xlsx(self, raw_bytes):
        with zipfile.ZipFile(io.BytesIO(raw_bytes)) as zf:
            shared_strings = []
            if 'xl/sharedStrings.xml' in zf.namelist():
                root = ET.fromstring(zf.read('xl/sharedStrings.xml'))
                ns = {'x': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
                for si in root.findall('x:si', ns):
                    shared_strings.append(''.join(t.text or '' for t in si.findall('.//x:t', ns)))
            sheet_path = self._resolve_sheet_path(zf)
            if sheet_path not in zf.namelist():
                raise UserError(_('XLSX sheet path not found: %s') % sheet_path)
            sheet = ET.fromstring(zf.read(sheet_path))
            ns = {'x': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
            rows = []
            for row in sheet.findall('.//x:sheetData/x:row', ns):
                vals = []
                for c in row.findall('x:c', ns):
                    cell_type = c.attrib.get('t')
                    value = c.find('x:v', ns)
                    if value is None:
                        vals.append('')
                    elif cell_type == 's':
                        idx = int(value.text)
                        vals.append(shared_strings[idx] if idx < len(shared_strings) else '')
                    else:
                        vals.append(value.text or '')
                rows.append(vals)
            return rows

    def _read_rows(self):
        self.ensure_one()
        raw = base64.b64decode(self.file_data)
        file_name = (self.file_name or '').lower()
        if file_name.endswith('.xlsx'):
            rows = self._iter_rows_xlsx(raw)
            if not rows:
                raise UserError(_('XLSX is empty.'))
            headers = [h.strip() for h in rows[0]]
            return headers, [
                {headers[i]: row[i] if i < len(row) else '' for i in range(len(headers))}
                for row in rows[1:]
            ]
        stream = io.StringIO(raw.decode('utf-8-sig'))
        reader = csv.DictReader(stream)
        return reader.fieldnames or [], list(reader)

    def _normalized_keys(self, fieldnames):
        aliases = {
            'invoice_ref': {'invoice_ref', 'invoice', 'invoice_no', 'number', 'ref'},
            'partner': {'partner', 'partner_name', 'customer', 'vendor', 'supplier'},
            'invoice_date': {'invoice_date', 'date', 'bill_date'},
            'product': {'product', 'product_name', 'item'},
            'description': {'description', 'name', 'line_description'},
            'quantity': {'quantity', 'qty'},
            'price_unit': {'price_unit', 'unit_price', 'price'},
            'tax': {'tax', 'tax_name', 'taxes'},
        }
        lower_map = {h.lower().strip(): h for h in fieldnames}
        keys = {}
        for target, alias_set in aliases.items():
            for alias in alias_set:
                if alias in lower_map:
                    keys[target] = lower_map[alias]
                    break
        return keys

    def _get_journal(self):
        if self.journal_id:
            return self.journal_id
        journal_type = 'sale' if self.move_type == 'out_invoice' else 'purchase'
        journal = self.env['account.journal'].search([
            ('company_id', '=', self.company_id.id),
            ('type', '=', journal_type),
        ], limit=1)
        if not journal:
            raise UserError(_('No %s journal found for company %s.') % (
                journal_type,
                self.company_id.display_name,
            ))
        return journal

    def _get_partner(self, name):
        partner_name = (name or '').strip()
        if not partner_name:
            raise UserError(_('Partner is required.'))
        partner = self.env['res.partner'].search([
            ('name', '=', partner_name),
        ], limit=1)
        if not partner:
            partner = self.env['res.partner'].create({
                'name': partner_name,
                'company_type': 'company',
            })
        return partner

    def _get_product(self, name):
        product_name = (name or '').strip()
        if not product_name:
            return self.env['product.product']
        product = self.env['product.product'].search([
            '|',
            ('default_code', '=', product_name),
            ('name', '=', product_name),
        ], limit=1)
        if not product:
            product = self.env['product.product'].create({
                'name': product_name,
                'type': 'service',
            })
        return product

    def _get_taxes(self, value):
        tax_name = (value or '').strip()
        if not tax_name:
            return []
        taxes = self.env['account.tax'].search([
            ('company_id', '=', self.company_id.id),
            ('name', '=', tax_name),
        ])
        if not taxes:
            raise UserError(_('Tax not found: %s') % tax_name)
        return taxes.ids

    def action_import(self):
        self.ensure_one()
        headers, rows = self._read_rows()
        keys = self._normalized_keys(headers)
        required = {'invoice_ref', 'partner', 'product'}
        if not required.issubset(keys):
            raise UserError(_(
                'File must include headers compatible with: invoice_ref, partner, product '
                '(optional: invoice_date, description, quantity, price_unit, tax).'
            ))
        journal = self._get_journal()
        grouped = {}
        sequence = []
        for row in rows:
            invoice_ref = (row.get(keys['invoice_ref']) or '').strip()
            if not invoice_ref:
                continue
            if invoice_ref not in grouped:
                grouped[invoice_ref] = {
                    'partner_name': row.get(keys['partner']) or '',
                    'invoice_date': row.get(keys.get('invoice_date')) if keys.get('invoice_date') else False,
                    'lines': [],
                }
                sequence.append(invoice_ref)
            product = self._get_product(row.get(keys['product']))
            description = row.get(keys.get('description')) if keys.get('description') else ''
            quantity = float(row.get(keys.get('quantity')) or 1.0) if keys.get('quantity') else 1.0
            price_unit = float(row.get(keys.get('price_unit')) or product.lst_price or 0.0) if keys.get('price_unit') else product.lst_price
            if quantity <= 0:
                raise UserError(_('Quantity must be positive for invoice %s.') % invoice_ref)
            line_vals = {
                'product_id': product.id,
                'name': description or product.display_name,
                'quantity': quantity,
                'price_unit': price_unit,
            }
            if keys.get('tax'):
                line_vals['tax_ids'] = [(6, 0, self._get_taxes(row.get(keys['tax'])))]
            grouped[invoice_ref]['lines'].append((0, 0, line_vals))
        if not sequence:
            raise UserError(_('No invoice rows found.'))
        moves = self.env['account.move']
        for invoice_ref in sequence:
            data = grouped[invoice_ref]
            partner = self._get_partner(data['partner_name'])
            vals = {
                'move_type': self.move_type,
                'company_id': self.company_id.id,
                'journal_id': journal.id,
                'partner_id': partner.id,
                'ref': invoice_ref,
                'invoice_line_ids': data['lines'],
                'gara_document_group_id': self.gara_document_group_id.id,
                'gara_document_reason_id': self.gara_document_reason_id.id,
                'gara_document_note': _('Imported from %s') % (self.file_name or 'file'),
            }
            if data['invoice_date']:
                vals['invoice_date'] = data['invoice_date']
            moves |= self.env['account.move'].create(vals)
        return {
            'type': 'ir.actions.act_window',
            'name': _('Imported invoices'),
            'res_model': 'account.move',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', moves.ids)],
        }
