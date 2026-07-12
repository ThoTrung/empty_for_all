# -*- coding: utf-8 -*-
# from odoo import http

from odoo import http, fields
from odoo.http import request, Response, send_file
import io
import os
import pprint
import tempfile
import subprocess
from urllib.parse import quote
from openpyxl import load_workbook
from datetime import datetime, date
from ..helper.transport_matrix_export import build_transport_matrix_xlsx_bytes
from ..helper.import_transport_matrix import build_import_template_bytes
from odoo.exceptions import UserError
from docxtpl import DocxTemplate
from ..services import rental_contract_services as rcs
from docx2pdf import convert
from docxtpl.richtext import RichText
import zipfile
import base64
import io


class RentalContractController(http.Controller):
    @http.route('/rental/rental-contract/quotation/<int:contract_id>/download', type='http', auth='user')
    def download_quotation_xlsx(self, contract_id):
        """Generate Excel file based on template"""
        contract = request.env['rental.contract'].sudo().browse(contract_id)
        if not contract.exists():
            return request.not_found()

        user = request.env.user
        is_internal = user.has_group('base.group_user')
        if not is_internal:
            return request.redirect('/my')

        data, _source = request.env["rental.template"].sudo().get_template_bytes(
            contract.company_id,
            "contract_quotation_xlsx",
        )
        wb = load_workbook(io.BytesIO(data))
        ws = wb.active
        # --- Replace placeholders ---
        replacements = {
            '{{b_company}}': contract.b_party.parent_id.name or '',
            '{{b_address}}': contract.b_address or '',
            '{{b_representative}}': contract.b_name or '',
            '{{b_phone}}': contract.b_phone or '',
            '{{b_email}}': contract.b_party.email or '',
            '{{today_is}}': date.today().strftime('ngày %d tháng %m năm %Y'),

            '{{a_representative}}': contract.a_name or '',
            '{{a_company}}': contract.a_party.parent_id.name or '',

            '{{construction_work_project}}': contract.construction_work_project_id.name or '',
            '{{construction_work_name}}': contract.construction_work_id.name or '',
            '{{construction_work_address}}': contract.construction_work_address or '',
        }

        for row in ws.iter_rows():
            for cell in row:
                if isinstance(cell.value, str):
                    for key, val in replacements.items():
                        if key in cell.value:
                            cell.value = cell.value.replace(key, val)

        # --- Find item table and duplicate rows ---
        start_row = 12  # example: first line template
        max_row = 100
        n = len(contract.rental_contract_line_ids)
        # for row_num in reversed(range(start_row + n, start_row + max_row)):
        #     ws.delete_rows(row_num)
        #     del ws.row_dimensions[row_num]
        for i, line in enumerate(contract.rental_contract_line_ids):
            r = start_row + i
            ws.cell(r, 1).value = i + 1
            ws.cell(r, 2).value = line.product_tmpl_id.display_name
            ws.cell(r, 3).value = line.uom_id.name
            ws.cell(r, 4).value = 1
            ws.cell(r, 5).value = line.price_unit * 30
            ws.cell(r, 6).value = line.price_unit * 1
            ws.cell(r, 7).value = line.product_tmpl_id.compensation_price

        for r in range(start_row + n, start_row + max_row):
            ws.row_dimensions[r].hidden = True
        # --- Save to memory ---
        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)

        # Prepare response
        filename = f"BẢNG BÁO GIÁ VẬT TƯ {contract.code}.xlsx"
        filename_ascii = quote(filename)  # URL-encode UTF-8 string
        headers = [
            ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
            ('Content-Disposition', f"attachment; filename*=UTF-8''{filename_ascii}")
        ]
        return request.make_response(buffer.read(), headers)

    @http.route('/rental/rental-contract/contract/<int:contract_id>/download', type='http', auth='user')
    def download_rental_contract_docx(self, contract_id):
        contract = request.env['rental.contract'].sudo().browse(contract_id)
        if not contract.exists():
            return request.not_found()

        user = request.env.user
        is_internal = user.has_group('base.group_user')
        if not is_internal:
            return request.redirect('/my')

        doc = rcs.render_rental_contract_docx(contract)

        # Prepare in-memory output
        output = io.BytesIO()
        doc.save(output)
        output.seek(0)

        # Prepare response
        label = contract.contract_number or contract.code
        filename = f"Hợp đồng_{label}.docx"
        filename_ascii = quote(filename)  # URL-encode UTF-8 string
        headers = [
            ('Content-Type', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'),
            ('Content-Disposition', f"inline; filename*=UTF-8''{filename_ascii}")
            # ('Content-Disposition', f"attachment; filename*=UTF-8''{filename_ascii}")
        ]
        return request.make_response(output.read(), headers)

    @http.route('/rental/rental-contract/contract/<int:contract_id>/print', type='http', auth='user')
    def print_rental_contract_docx(self, contract_id):
        contract = request.env['rental.contract'].sudo().browse(contract_id)
        if not contract.exists():
            return request.not_found()

        user = request.env.user
        is_internal = user.has_group('base.group_user')
        if not is_internal:
            return request.redirect('/my')

        doc = rcs.render_rental_contract_docx(contract)

        with tempfile.TemporaryDirectory() as temp_dir:
            output_docx_path = os.path.join(temp_dir, f'print_rental_contract_{contract.id}.docx')
            output_pdf_path = os.path.join(temp_dir, f'print_rental_contract_{contract.id}.pdf')
            doc.save(output_docx_path)
            try:
                subprocess.run(
                    [
                        'libreoffice',
                        '--headless',
                        '--convert-to',
                        'pdf',
                        '--outdir',
                        temp_dir,
                        output_docx_path,
                    ],
                    check=True,
                    capture_output=True,
                    text=True
                )
            except (subprocess.CalledProcessError, FileNotFoundError) as e:
                # Capture and report any conversion errors
                raise UserError(
                    f"Error converting document to PDF with LibreOffice: {e.stderr}"
                    if isinstance(e, subprocess.CalledProcessError)
                    else f"LibreOffice not found. Is it installed? Error: {e}"
                )

            with open(output_pdf_path, 'rb') as pdf_file:
                pdf_data = pdf_file.read()

        label = contract.contract_number or contract.code
        filename = f"Hợp đồng_{label}.pdf"
        filename_ascii = quote(filename)  # URL-encode UTF-8 string
        headers = [
            ('Content-Type', 'application/pdf'),
            ('Content-Disposition', f'inline; filename="{filename_ascii}.pdf"'),
        ]

        response = request.make_response(pdf_data, headers=headers)
        return response

    @http.route('/rental/rental-contract/transport-matrix/<int:contract_id>/download', type='http', auth='user')
    def download_rental_contract_transport_matrix_xlsx(self, contract_id, **kw):
        start_date = fields.Date.from_string(kw.get('start_date'))
        end_date = fields.Date.from_string(kw.get('end_date'))
        contract = request.env['rental.contract'].sudo().browse(contract_id)
        if not contract.exists():
            return request.not_found()

        user = request.env.user
        is_internal = user.has_group('base.group_user')
        if not is_internal:
            return request.redirect('/my')

        xlsx_bytes = build_transport_matrix_xlsx_bytes(
            request.env, contract, start_date, end_date,
        )

        filename = f"KLCT {end_date.strftime('%m-%Y')} - {contract.code}.xlsx"
        filename_ascii = quote(filename)
        headers = [
            ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
            ('Content-Disposition', f"attachment; filename*=UTF-8''{filename_ascii}")
        ]
        return request.make_response(xlsx_bytes, headers)

    @http.route('/rental/transport-matrix/<int:matrix_id>/download', type='http', auth='user')
    def download_transport_matrix_from_record(self, matrix_id, **kw):
        """
        Download the transport matrix XLSX based on a persisted rental.transport.matrix record.
        """
        matrix = request.env['rental.transport.matrix'].sudo().browse(matrix_id)
        if not matrix.exists():
            return request.not_found()

        user = request.env.user
        is_internal = user.has_group('base.group_user')
        if not is_internal:
            return request.redirect('/my')

        # Reuse the existing generator by calling the same logic with contract_id + dates
        params = {
            "start_date": fields.Date.to_string(matrix.start_date),
            "end_date": fields.Date.to_string(matrix.end_date),
        }
        return self.download_rental_contract_transport_matrix_xlsx(matrix.rental_contract_id.id, **params)

    @http.route(
        '/rental/rental-contract/transport-import-template/<int:contract_id>/download',
        type='http',
        auth='user',
    )
    def download_transport_import_template_xlsx(self, contract_id, **kw):
        contract = request.env['rental.contract'].browse(contract_id)
        if not contract.exists():
            return request.not_found()

        user = request.env.user
        if not user.has_group('rental.group_rental_staff'):
            return request.redirect('/my')

        buffer = io.BytesIO(build_import_template_bytes(contract, request.env))
        buffer.seek(0)
        filename = f"BIỂU MẪU IMPORT XUẤT NHẬP KHO {contract.code}.xlsx"
        filename_ascii = quote(filename)
        headers = [
            ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
            ('Content-Disposition', f"attachment; filename*=UTF-8''{filename_ascii}"),
        ]
        return request.make_response(buffer.read(), headers)

    # @http.route('/rental/rental-contract/invoice/<int:contract_id>/download', type='http', auth='user')
    # def download_rental_contract_invoice_xlsx(self, contract_id, **kw):
    #     start_date = fields.Date.from_string(kw.get('start_date'))
    #     end_date = fields.Date.from_string(kw.get('end_date'))
    #     user = request.env.user
    #     is_internal = user.has_group('base.group_user')
    #     if not is_internal:
    #         return request.redirect('/my')
    #
    #     contract = request.env['rental.contract'].sudo().browse(contract_id)
    #     if not contract.exists():
    #         return request.not_found()
    #
    #
    #
    #     headers = [
    #         ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
    #         ('Content-Disposition', f"attachment; filename*=UTF-8''{filename_ascii}")
    #     ]
    #     return request.make_response(buffer.read(), headers)
