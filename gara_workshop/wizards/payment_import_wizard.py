# -*- coding: utf-8 -*-

import base64
import csv
import io
import zipfile
import xml.etree.ElementTree as ET

from odoo import fields, models, _
from odoo.exceptions import UserError


class GaraPaymentImportWizard(models.TransientModel):
    _name = 'gara.payment.import.wizard'
    _description = 'Import workshop payments from CSV'

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
    )
    create_account_payment = fields.Boolean(
        string='Register in Accounting',
        help='If set, each row also creates and posts a customer payment (account.payment) on the selected journal.',
    )
    payment_journal_id = fields.Many2one(
        'account.journal',
        string='Payment journal',
        domain="[('type', 'in', ('bank', 'cash')), ('company_id', '=', company_id)]",
        help='Bank or cash journal used when registering accounting payments.',
    )
    file_data = fields.Binary(required=True)
    file_name = fields.Char()
    xlsx_sheet_name = fields.Char(
        string='XLSX sheet path',
        default='xl/worksheets/sheet1.xml',
        help='Advanced: sheet XML path inside xlsx zip (default first sheet path).',
    )
    xlsx_sheet_label = fields.Char(
        string='XLSX sheet name',
        help='Optional human sheet name (e.g. Sheet1). If set, it overrides sheet path.',
    )

    def _resolve_sheet_path(self, zf):
        if self.xlsx_sheet_label:
            ns = {'x': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
            rel_ns = {'r': 'http://schemas.openxmlformats.org/package/2006/relationships'}
            wb = ET.fromstring(zf.read('xl/workbook.xml'))
            rel = ET.fromstring(zf.read('xl/_rels/workbook.xml.rels'))
            rid = None
            for sheet in wb.findall('.//x:sheets/x:sheet', ns):
                if (sheet.attrib.get('name') or '').strip() == self.xlsx_sheet_label.strip():
                    rid = sheet.attrib.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
                    break
            if not rid:
                raise UserError(_('Sheet name not found: %s') % self.xlsx_sheet_label)
            target = None
            for node in rel.findall('.//r:Relationship', rel_ns):
                if node.attrib.get('Id') == rid:
                    target = node.attrib.get('Target')
                    break
            if not target:
                raise UserError(_('Cannot resolve sheet relation for: %s') % self.xlsx_sheet_label)
            if not target.startswith('worksheets/'):
                raise UserError(_('Unsupported sheet target path: %s') % target)
            return 'xl/' + target
        return self.xlsx_sheet_name or 'xl/worksheets/sheet1.xml'

    def _create_customer_payment(self, case, amount, payment_date, memo):
        self.ensure_one()
        journal = self.payment_journal_id
        if not journal:
            journal = self.env['account.journal'].search(
                [
                    ('company_id', '=', case.company_id.id),
                    ('type', 'in', ('bank', 'cash')),
                ],
                limit=1,
            )
        if not journal:
            raise UserError(_('No bank or cash journal found for company %s.') % case.company_id.display_name)
        method_line = journal.inbound_payment_method_line_ids[:1]
        if not method_line:
            raise UserError(_('Journal %s has no inbound payment method.') % journal.display_name)
        partner = case.partner_id.with_company(case.company_id)
        destination = partner.property_account_receivable_id
        if not destination:
            destination = self.env['account.account'].search(
                [
                    ('company_id', '=', case.company_id.id),
                    ('account_type', '=', 'asset_receivable'),
                ],
                limit=1,
            )
        if not destination:
            raise UserError(_('No receivable account for partner %s.') % partner.display_name)
        pay = self.env['account.payment'].create({
            'amount': amount,
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'partner_id': partner.id,
            'date': payment_date,
            'journal_id': journal.id,
            'payment_method_line_id': method_line.id,
            'destination_account_id': destination.id,
            'payment_reference': memo or case.name,
            'gara_case_id': case.id,
        })
        pay.action_post()
        return pay

    def _iter_rows_xlsx(self, raw_bytes):
        """Minimal XLSX parser (single sheet) without third-party deps."""
        with zipfile.ZipFile(io.BytesIO(raw_bytes)) as zf:
            shared_strings = []
            if 'xl/sharedStrings.xml' in zf.namelist():
                root = ET.fromstring(zf.read('xl/sharedStrings.xml'))
                ns = {'x': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
                for si in root.findall('x:si', ns):
                    text = ''.join(t.text or '' for t in si.findall('.//x:t', ns))
                    shared_strings.append(text)
            sheet_path = self._resolve_sheet_path(zf)
            if sheet_path not in zf.namelist():
                raise UserError(_('XLSX sheet path not found: %s') % sheet_path)
            sheet = ET.fromstring(zf.read(sheet_path))
            ns = {'x': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
            rows = []
            for row in sheet.findall('.//x:sheetData/x:row', ns):
                vals = []
                for c in row.findall('x:c', ns):
                    t = c.attrib.get('t')
                    v = c.find('x:v', ns)
                    if v is None:
                        vals.append('')
                        continue
                    if t == 's':
                        idx = int(v.text)
                        vals.append(shared_strings[idx] if idx < len(shared_strings) else '')
                    else:
                        vals.append(v.text or '')
                rows.append(vals)
            return rows

    def action_import(self):
        self.ensure_one()
        if not self.file_data:
            raise UserError(_('Please upload a CSV file.'))
        raw = base64.b64decode(self.file_data)
        fname = (self.file_name or '').lower()
        if fname.endswith('.xlsx'):
            rows = self._iter_rows_xlsx(raw)
            if not rows:
                raise UserError(_('XLSX is empty.'))
            headers = [h.strip() for h in rows[0]]
            reader = []
            for row in rows[1:]:
                vals = {headers[i]: row[i] if i < len(row) else '' for i in range(len(headers))}
                reader.append(vals)
            fieldnames = headers
        else:
            stream = io.StringIO(raw.decode('utf-8-sig'))
            csv_reader = csv.DictReader(stream)
            fieldnames = csv_reader.fieldnames
            reader = list(csv_reader)
        aliases = {
            'case_ref': {'case_ref', 'case', 'case_reference', 'case no', 'case_no', 'ref'},
            'amount': {'amount', 'payment_amount', 'money'},
            'payment_date': {'payment_date', 'date', 'paid_date'},
            'note': {'note', 'memo', 'description'},
        }
        lower_map = {h.lower().strip(): h for h in (fieldnames or [])}
        normalized_keys = {}
        for target, alias_set in aliases.items():
            for alias in alias_set:
                if alias in lower_map:
                    normalized_keys[target] = lower_map[alias]
                    break
        required = {'case_ref', 'amount'}
        if not fieldnames or not required.issubset(set(normalized_keys.keys())):
            raise UserError(_('File must include headers compatible with: case_ref, amount (optional: payment_date, note).'))
        Payment = self.env['gara.workshop.payment']
        Case = self.env['gara.workshop.case']
        created = 0
        if self.create_account_payment and not self.payment_journal_id:
            if not self.env['account.journal'].search_count([
                ('company_id', '=', self.company_id.id),
                ('type', 'in', ('bank', 'cash')),
            ]):
                raise UserError(_('Register in Accounting is enabled but no bank/cash journal exists for this company.'))
        for line in reader:
            case_ref = (line.get(normalized_keys['case_ref']) or '').strip()
            if not case_ref:
                continue
            case = Case.search([('name', '=', case_ref), ('company_id', '=', self.company_id.id)], limit=1)
            if not case:
                raise UserError(_('Case ref not found: %s') % case_ref)
            amount = float(line.get(normalized_keys['amount']) or 0)
            if amount <= 0:
                raise UserError(_('Amount must be positive for case %s') % case_ref)
            vals = {
                'case_id': case.id,
                'partner_id': case.partner_id.id,
                'amount': amount,
            }
            date_key = normalized_keys.get('payment_date')
            note_key = normalized_keys.get('note')
            pay_date = fields.Date.context_today(self)
            if date_key and line.get(date_key):
                vals['payment_date'] = line[date_key]
                pay_date = vals['payment_date']
            if note_key and line.get(note_key):
                vals['note'] = line[note_key]
            memo = vals.get('note') or ''
            if self.create_account_payment:
                pay = self._create_customer_payment(case, amount, pay_date, memo)
                vals['account_payment_id'] = pay.id
            Payment.create(vals)
            case._log_audit(
                'import_payment_csv',
                f'Imported payment {amount}' + (' + account.payment' if self.create_account_payment else ''),
            )
            created += 1
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Import completed'),
                'message': _('%s payment line(s) imported.') % created,
                'sticky': False,
                'type': 'success',
            }
        }
