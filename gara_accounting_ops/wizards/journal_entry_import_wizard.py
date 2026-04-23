# -*- coding: utf-8 -*-

import base64
import csv
import io
import zipfile
import xml.etree.ElementTree as ET

from odoo import fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_compare


class GaraJournalEntryImportWizard(models.TransientModel):
    _name = 'gara.journal.entry.import.wizard'
    _description = 'Import journal entries from CSV/XLSX'

    company_id = fields.Many2one(
        'res.company',
        required=True,
        default=lambda self: self.env.company,
    )
    journal_id = fields.Many2one(
        'account.journal',
        required=True,
        domain="[('company_id', '=', company_id), ('type', '=', 'general')]",
        default=lambda self: self._default_journal(),
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

    def _default_journal(self):
        return self.env['account.journal'].search([
            ('company_id', '=', self.env.company.id),
            ('type', '=', 'general'),
        ], limit=1)

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
            'entry_ref': {'entry_ref', 'entry', 'move_ref', 'journal_ref', 'number', 'ref'},
            'date': {'date', 'entry_date', 'accounting_date'},
            'account': {'account', 'account_code', 'account_number', 'tk'},
            'label': {'label', 'name', 'description', 'memo'},
            'partner': {'partner', 'partner_name'},
            'debit': {'debit', 'debit_amount', 'no', 'nợ'},
            'credit': {'credit', 'credit_amount', 'co', 'có'},
        }
        lower_map = {h.lower().strip(): h for h in fieldnames}
        keys = {}
        for target, alias_set in aliases.items():
            for alias in alias_set:
                if alias in lower_map:
                    keys[target] = lower_map[alias]
                    break
        return keys

    def _get_account(self, code):
        account_code = (code or '').strip()
        if not account_code:
            raise UserError(_('Account code is required.'))
        account = self.env['account.account'].search([
            ('company_id', '=', self.company_id.id),
            ('code', '=', account_code),
            ('deprecated', '=', False),
        ], limit=1)
        if not account:
            raise UserError(_('Account not found or deprecated: %s') % account_code)
        return account

    def _get_partner(self, name):
        partner_name = (name or '').strip()
        if not partner_name:
            return self.env['res.partner']
        partner = self.env['res.partner'].search([
            ('name', '=', partner_name),
        ], limit=1)
        if not partner:
            partner = self.env['res.partner'].create({
                'name': partner_name,
                'company_type': 'company',
            })
        return partner

    def _amount(self, value):
        text = (value or '').strip()
        if not text:
            return 0.0
        return float(text.replace(',', ''))

    def _line_from_row(self, row, keys, entry_ref):
        debit = self._amount(row.get(keys['debit']))
        credit = self._amount(row.get(keys['credit']))
        if debit < 0 or credit < 0:
            raise UserError(_('Debit/Credit must be non-negative for entry %s.') % entry_ref)
        if debit and credit:
            raise UserError(_('A line cannot have both debit and credit for entry %s.') % entry_ref)
        if not debit and not credit:
            raise UserError(_('A line must have either debit or credit for entry %s.') % entry_ref)
        partner = self._get_partner(row.get(keys.get('partner')) if keys.get('partner') else '')
        vals = {
            'account_id': self._get_account(row.get(keys['account'])).id,
            'name': row.get(keys.get('label')) if keys.get('label') else '/',
            'debit': debit,
            'credit': credit,
        }
        if partner:
            vals['partner_id'] = partner.id
        return (0, 0, vals)

    def action_import(self):
        self.ensure_one()
        headers, rows = self._read_rows()
        keys = self._normalized_keys(headers)
        required = {'entry_ref', 'account', 'debit', 'credit'}
        if not required.issubset(keys):
            raise UserError(_(
                'File must include headers compatible with: entry_ref, account, debit, credit '
                '(optional: date, label, partner).'
            ))
        grouped = {}
        sequence = []
        for row in rows:
            entry_ref = (row.get(keys['entry_ref']) or '').strip()
            if not entry_ref:
                continue
            if entry_ref not in grouped:
                grouped[entry_ref] = {
                    'date': row.get(keys.get('date')) if keys.get('date') else fields.Date.today(),
                    'lines': [],
                    'debit': 0.0,
                    'credit': 0.0,
                }
                sequence.append(entry_ref)
            line = self._line_from_row(row, keys, entry_ref)
            grouped[entry_ref]['lines'].append(line)
            grouped[entry_ref]['debit'] += line[2]['debit']
            grouped[entry_ref]['credit'] += line[2]['credit']
        if not sequence:
            raise UserError(_('No journal entry rows found.'))
        moves = self.env['account.move']
        precision_rounding = self.company_id.currency_id.rounding
        for entry_ref in sequence:
            data = grouped[entry_ref]
            if float_compare(data['debit'], data['credit'], precision_rounding=precision_rounding):
                raise UserError(_('Entry %s is not balanced.') % entry_ref)
            moves |= self.env['account.move'].create({
                'move_type': 'entry',
                'company_id': self.company_id.id,
                'journal_id': self.journal_id.id,
                'date': data['date'],
                'ref': entry_ref,
                'line_ids': data['lines'],
                'gara_document_group_id': self.gara_document_group_id.id,
                'gara_document_reason_id': self.gara_document_reason_id.id,
                'gara_document_note': _('Imported from %s') % (self.file_name or 'file'),
            })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Imported journal entries'),
            'res_model': 'account.move',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', moves.ids)],
        }
