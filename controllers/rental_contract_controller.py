# -*- coding: utf-8 -*-
# from odoo import http

from collections import OrderedDict

from odoo import http, fields
from odoo.http import request, Response, send_file
from openpyxl.styles import Font, PatternFill
from odoo.addons.rental.models import rental_transport_matrix as rtm
import io
import os
import pprint
import tempfile
import subprocess
from urllib.parse import quote
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter
from datetime import datetime, date
from ..helper.export_excel_template import insert_rows_below, extend_product_column_styles
from ..helper.import_transport_matrix import build_import_template_bytes
from ..helper.xlsx_template_utils import (
    apply_product_column_styles,
    find_transport_matrix_layout,
    replace_placeholders_in_sheet,
)
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
        filename = f"Hợp đồng_{contract.name}.docx"
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

        filename = f"Hợp đồng_{contract.name}.pdf"
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

        # Trong kỳ [start_date, end_date]
        rr_transport_ids = contract.rr_transport_ids.filtered_domain([
            ('start_rental_or_return_date', '>=', start_date),
            ('start_rental_or_return_date', '<=', end_date),
        ])
        # Trước start_date → dòng "Tồn đầu kỳ"
        rr_transport_ids_before = contract.rr_transport_ids.filtered_domain([
            ('start_rental_or_return_date', '<', start_date),
        ])

        user = request.env.user
        is_internal = user.has_group('base.group_user')
        if not is_internal:
            return request.redirect('/my')

        def _cells_from_transports(transport_set):
            cell_qty = {}
            for transport in transport_set:
                for line in transport.transport_line_ids:
                    if not line.product_id:
                        continue
                    key = (line.product_tmpl_id.id, line.product_id.id)
                    cell_qty[key] = cell_qty.get(key, 0) + (line.qty or 0)
            return cell_qty

        opening_cells = _cells_from_transports(rr_transport_ids_before)
        has_opening = any(v != 0 for v in opening_cells.values())

        # product_tmpls từ cả trước kỳ và trong kỳ (giống bảng HTML; thứ tự template ổn định)
        product_tmpls = OrderedDict()
        for transport in rr_transport_ids_before | rr_transport_ids:
            for line in transport.transport_line_ids:
                if not line.product_tmpl_id or not line.product_id:
                    continue
                product_tmpl = product_tmpls.get(line.product_tmpl_id.id, False)
                product = {
                    'id': line.product_id.id,
                    'name': line.product_id.display_name,
                    'variant_name': line.product_id.product_template_variant_value_ids.name,
                    'price_multiplier': rtm._variant_price_multiplier(line.product_id),
                }
                if not product_tmpl:
                    product_tmpl = {
                        'product_tmpl_id': line.product_tmpl_id.id,
                        'product_tmpl_name': line.product_tmpl_id.display_name,
                        'products': {line.product_id.id: product},
                    }
                else:
                    product_tmpl['products'][line.product_id.id] = product
                product_tmpls[line.product_tmpl_id.id] = product_tmpl

        for _p_tmpl_id, p_tmpl in product_tmpls.items():
            p_tmpl['products'] = dict(rtm._sort_products_odict(OrderedDict(p_tmpl['products'])))

        env = request.env
        groups_meta = []
        for p_tmpl_id, p_tmpl in product_tmpls.items():
            prod_order = list(p_tmpl['products'].keys())
            prods = p_tmpl['products']
            needs_md = rtm._group_needs_md_column(env, prods, prod_order)
            groups_meta.append({
                'tmpl_id': p_tmpl_id,
                'p_tmpl': p_tmpl,
                'prod_order': prod_order,
                'needs_md': needs_md,
            })

        product_ids_2_col = {}
        md_col_by_tmpl = {}
        col_idx = 4
        for g in groups_meta:
            p_tmpl_id = g['tmpl_id']
            p_tmpl = g['p_tmpl']
            if g['needs_md']:
                for prod_id in g['prod_order']:
                    product_ids_2_col[f"{p_tmpl_id}_{prod_id}"] = col_idx
                    col_idx += 1
                md_col_by_tmpl[p_tmpl_id] = col_idx
                col_idx += 1
            else:
                prod_id = g['prod_order'][0]
                product_ids_2_col[f"{p_tmpl_id}_{prod_id}"] = col_idx
                col_idx += 1
        last_product_col = col_idx - 1

        # Tổng cuối = Tồn đầu kỳ + tổng trong kỳ
        total_cells = dict((k, v) for k, v in opening_cells.items())
        for transport in rr_transport_ids:
            for line in transport.transport_line_ids:
                if not line.product_id:
                    continue
                key = (line.product_tmpl_id.id, line.product_id.id)
                total_cells[key] = total_cells.get(key, 0) + (line.qty or 0)

        data, _source = request.env["rental.template"].sudo().get_template_bytes(
            contract.company_id,
            "transport_matrix_xlsx",
        )
        wb = load_workbook(io.BytesIO(data))
        ws = wb.active
        replacements = {
            '{{b_company}}': contract.b_party.parent_id.name or '',
            '{{b_address}}': contract.b_address or '',
            '{{b_representative}}': contract.b_name or '',
            '{{b_function}}': contract.b_function or '',
            '{{a_representative}}': contract.a_name or '',
            '{{a_company}}': contract.a_party.parent_id.name or '',
            '{{a_function}}': contract.a_function or '',
            '{{construction_work_project}}': contract.construction_work_project_id.name or '',
            '{{construction_work_name}}': contract.construction_work_id.name or '',
            '{{construction_work_address}}': contract.construction_work_address or '',
        }
        replace_placeholders_in_sheet(ws, replacements)

        title_row, header_second_row, header_third_row, start_row = find_transport_matrix_layout(ws)
        start_product_col = 4
        template_last_product_col = 23  # column W in default template
        cur_product_col = start_product_col
        md_fill = PatternFill(start_color="E8F5E9", end_color="E8F5E9", fill_type="solid")

        def _xlsx_md_sum(cell_qty_map, tmpl_id, p_tmpl):
            total = 0.0
            for prod_id in p_tmpl['products']:
                prod_rec = env['product.product'].browse(prod_id)
                length = rtm._linear_meter_factor_for_product(prod_rec)
                if length is None:
                    continue
                q = cell_qty_map.get((tmpl_id, prod_id), 0) or 0
                total += q * length
            return total

        def _xlsx_md_cell_value(total):
            if total is None or abs(total) < 1e-12:
                return None
            if abs(total - round(total)) < 1e-9:
                return int(round(total))
            return round(float(total), 2)

        def _write_md_cells(r, cell_qty_map):
            for g in groups_meta:
                if not g['needs_md']:
                    continue
                p_tmpl_id = g['tmpl_id']
                mcol = md_col_by_tmpl.get(p_tmpl_id)
                if mcol:
                    mdv = _xlsx_md_sum(cell_qty_map, p_tmpl_id, g['p_tmpl'])
                    ws.cell(r, mcol).value = _xlsx_md_cell_value(mdv)
                    ws.cell(r, mcol).fill = md_fill

        # Extend merged header "Chủng loại/ Khối lượng" through all product columns.
        for rng in list(ws.merged_cells.ranges):
            ref = str(rng)
            if (
                rng.min_row == title_row
                and rng.min_col >= start_product_col
                and rng.max_col >= start_product_col
            ):
                ws.unmerge_cells(ref)
        ws.merge_cells(
            start_row=title_row,
            start_column=start_product_col,
            end_row=title_row,
            end_column=last_product_col,
        )

        # Clear old product-header merges from template before rewriting columns.
        for rng in list(ws.merged_cells.ranges):
            if rng.min_row in (header_second_row, header_third_row) and rng.min_col >= start_product_col:
                ws.unmerge_cells(str(rng))

        for g in groups_meta:
            p_tmpl_id = g['tmpl_id']
            p_tmpl = g['p_tmpl']
            if g['needs_md']:
                span = len(g['prod_order']) + 1
                ws.merge_cells(
                    start_row=header_second_row,
                    start_column=cur_product_col,
                    end_row=header_second_row,
                    end_column=cur_product_col + span - 1,
                )
                ws.cell(header_second_row, cur_product_col).value = p_tmpl['product_tmpl_name']
                i = 0
                for prod_id in g['prod_order']:
                    prod = p_tmpl['products'][prod_id]
                    c = ws.cell(header_third_row, cur_product_col + i)
                    c.value = prod['variant_name'] or prod['name']
                    i += 1
                md_cell = ws.cell(header_third_row, cur_product_col + i)
                md_cell.value = "Tổng MD"
                md_cell.fill = md_fill
                cur_product_col += span
            else:
                prod_id = g['prod_order'][0]
                prod = p_tmpl['products'][prod_id]
                ws.merge_cells(
                    start_row=header_second_row,
                    start_column=cur_product_col,
                    end_row=header_third_row,
                    end_column=cur_product_col,
                )
                ws.cell(header_second_row, cur_product_col).value = prod['name']
                cur_product_col += 1

        max_row = 100
        row_idx = 0

        # 1) Dòng Tồn đầu kỳ (nếu có): merge cột 2-3, chữ đậm (giống dòng Tổng KL Cuối)
        if has_opening:
            r = start_row + row_idx
            ws.cell(r, 1).value = row_idx + 1
            cell_tondau = ws.cell(r, 2)
            cell_tondau.value = 'Tồn đầu kỳ'
            cell_tondau.font = Font(bold=True)
            ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=3)
            for (tmpl_id, prod_id), qty in opening_cells.items():
                col = product_ids_2_col.get(f'{tmpl_id}_{prod_id}')
                if col:
                    ws.cell(r, col).value = qty
            _write_md_cells(r, opening_cells)
            row_idx += 1

        # 2) Các dòng transport trong kỳ
        for transport in rr_transport_ids:
            r = start_row + row_idx
            ws.cell(r, 1).value = row_idx + 1
            ws.cell(r, 2).value = transport.start_rental_or_return_date.strftime('%-d/%-m/%Y')
            ws.cell(r, 3).value = transport.plate or ''
            cell_row = _cells_from_transports(transport)
            for (tmpl_id, prod_id), qty in cell_row.items():
                col = product_ids_2_col.get(f'{tmpl_id}_{prod_id}')
                if col:
                    ws.cell(r, col).value = qty
            _write_md_cells(r, cell_row)
            row_idx += 1

        # 3) Dòng Tổng KL Cuối T{MM.YYYY}
        r_total = start_row + row_idx
        ws.cell(r_total, 1).value = ''
        ws.cell(r_total, 2).value = f"Tổng KL Cuối T{end_date.strftime('%m.%Y')}"
        ws.merge_cells(start_row=r_total, start_column=2, end_row=r_total, end_column=3)
        for (tmpl_id, prod_id), qty in total_cells.items():
            col = product_ids_2_col.get(f'{tmpl_id}_{prod_id}')
            if col:
                ws.cell(r_total, col).value = qty
        _write_md_cells(r_total, total_cells)
        row_idx += 1

        data_end_row = start_row + row_idx - 1
        apply_product_column_styles(
            ws,
            start_col=start_product_col,
            last_col=last_product_col,
            header_rows=[header_second_row, header_third_row],
            ref_col=start_product_col,
            data_start_row=start_row,
            data_end_row=data_end_row,
            total_row=r_total,
            header_wrap=True,
        )
        # Cột "Tổng MD": đồng nhất với bảng xem trước (XML) — nền xanh nhạt + IN ĐẬM cho
        # toàn cột (tiêu đề + dữ liệu + dòng tổng). Đặt SAU apply_product_column_styles vì
        # hàm đó copy style từ cột tham chiếu (không đậm/không nền) đè lên các cột.
        def _md_bold_font(cell):
            base = cell.font
            return Font(name=base.name, size=base.size, bold=True, italic=base.italic, color=base.color)

        for mcol in md_col_by_tmpl.values():
            header_cell = ws.cell(header_third_row, mcol)
            header_cell.value = "Tổng MD"
            header_cell.fill = md_fill
            header_cell.font = _md_bold_font(header_cell)
            for r in range(start_row, r_total + 1):
                c = ws.cell(r, mcol)
                c.fill = md_fill
                if c.value not in (None, ""):
                    c.font = _md_bold_font(c)
        for col in range(start_product_col, last_product_col + 1):
            width = ws.column_dimensions[get_column_letter(col)].width
            if not width or width < 7:
                ws.column_dimensions[get_column_letter(col)].width = 7.0

        for r in range(start_row + row_idx, start_row + max_row):
            ws.row_dimensions[r].hidden = True
        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)

        # Prepare response
        filename = f"KLCT {end_date.strftime('%m-%Y')} - {contract.code}.xlsx"
        filename_ascii = quote(filename)  # URL-encode UTF-8 string
        headers = [
            ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
            ('Content-Disposition', f"attachment; filename*=UTF-8''{filename_ascii}")
        ]
        return request.make_response(buffer.read(), headers)

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
