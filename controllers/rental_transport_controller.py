# -*- coding: utf-8 -*-
# from odoo import http

from odoo import http, fields
from odoo.http import request, Response, send_file
import io
import pytz
import os
import pprint
import tempfile
import subprocess
from urllib.parse import quote
from openpyxl import load_workbook
from odoo.modules.module import get_module_resource
from datetime import datetime, date
from ..helper.export_excel_template import insert_rows_below
from odoo.exceptions import UserError
from docxtpl import DocxTemplate
from ..services import rental_contract_services as rcs
from docx2pdf import convert
from docxtpl.richtext import RichText
import zipfile
import base64
import io


class TransportController(http.Controller):
    @http.route('/rental/transport/equipment-delivery-receipt/<int:transport_id>/download', type='http', auth='user')
    def download_equipment_delivery_receipt_xlsx(self, transport_id):
        """Generate Excel file based on template"""
        transport = request.env['rr.transport'].sudo().browse(transport_id)
        if not transport.exists():
            return request.not_found()

        user = request.env.user
        is_internal = user.has_group('base.group_user')
        if not is_internal:
            return request.redirect('/my')

        data, _source = request.env["rental.template"].sudo().get_template_bytes(
            transport.company_id,
            "equipment_receipt_xlsx",
        )
        wb = load_workbook(io.BytesIO(data))
        ws = wb.active
        # --- Replace placeholders ---
        user_timezone = pytz.timezone(http.request.env.user.tz or 'UTC')
        replacements = {
            '{{dp_name}}': transport.dp_name or '',
            '{{dp_owner_name}}': transport.dp_owner_name or '',
            '{{dp_owner_function}}': transport.dp_owner_function or '',
            '{{dp_party_phone}}': transport.dp_party_phone or '',
            '{{deliverer_name}}': transport.deliverer_partner_id.name if transport.deliverer_partner_id else '',
            '{{deliverer_phone}}': transport.deliverer_phone or '',
            '{{deliverer_id_number}}': transport.deliverer_id_number or '',
            '{{deliverer_partner_function}}': transport.deliverer_partner_function or '',
            '{{rp_name}}': transport.rp_name or '',
            '{{rp_owner_name}}': transport.rp_owner_name or '',
            '{{rp_owner_function}}': transport.rp_owner_function or '',
            '{{rp_party_phone}}': transport.rp_party_phone or '',
            '{{receiver_name}}': transport.receiver_partner_id.name if transport.receiver_partner_id else '',
            '{{receiver_phone}}': transport.receiver_phone or '',
            '{{receiver_id_number}}': transport.receiver_id_number or '',
            '{{receiver_partner_function}}': transport.receiver_partner_function or '',

            '{{construction_work_project}}': transport.construction_work_project_id.name or '',
            '{{construction_work_name}}': transport.construction_work_id.name or '',
            '{{construction_work_address}}': transport.construction_work_address or '',

            '{{equipment_carrier}}': 'Bên thuê thực hiện' if transport.equipment_carrier == 'a_party_carrier' else 'Bên cho thuê thực hiện',
            '{{equipment_carrier_name}}': transport.equipment_carrier_name or '',

            '{{vehicle_start_time}}': transport.vehicle_start_time.astimezone(user_timezone).strftime("%Hh%M ngày %d/%m/%Y"),
            '{{vehicle_arrival_time}}': transport.vehicle_arrival_time.astimezone(user_timezone).strftime("%Hh%M ngày %d/%m/%Y") if transport.vehicle_arrival_time else '',

            '{{plate}}': transport.plate or '',
        }

        for row in ws.iter_rows():
            for cell in row:
                if isinstance(cell.value, str):
                    for key, val in replacements.items():
                        if key in cell.value:
                            cell.value = cell.value.replace(key, val)

        # --- Find item table and duplicate rows ---
        start_row = 22  # example: first line template
        max_row = 50
        n = len(transport.transport_line_ids)
        for i, line in enumerate(transport.transport_line_ids):
            r = start_row + i
            ws.cell(r, 1).value = i + 1
            ws.cell(r, 2).value = line.product_id.display_name
            ws.cell(r, 3).value = line.product_id._get_staff_display_uom().name
            ws.cell(r, 4).value = line.qty

        for r in range(start_row + n, start_row + max_row):
            ws.row_dimensions[r].hidden = True
        # --- Save to memory ---
        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)

        # Prepare response
        filename = f"BIÊN BẢN GIAO NHẬN THIẾT BỊ {transport.code}.xlsx"
        filename_ascii = quote(filename)  # URL-encode UTF-8 string
        headers = [
            ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
            ('Content-Disposition', f"attachment; filename*=UTF-8''{filename_ascii}")
        ]
        return request.make_response(buffer.read(), headers)
