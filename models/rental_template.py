# -*- coding: utf-8 -*-
import base64
import io

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.modules.module import get_module_resource

# Fallback static files when no company template is uploaded.
TEMPLATE_DEFAULT_FILES = {
    "contract_docx": "rental_contract_template.docx",
    "contract_quotation_xlsx": "quotation_template.xlsx",
    "transport_matrix_xlsx": "transport_matrix_template.xlsx",
    "transport_import_xlsx": "transport_import_template.xlsx",
    "rental_invoice_xlsx": "rental_invoice_template.xlsx",
    "debt_confirmation_xlsx": "debt_confirmation_comparison_table_template.xlsx",
    "equipment_receipt_xlsx": "equipment_delivery_receipt_template.xlsx",
}


class RentalTemplate(models.Model):
    _name = "rental.template"
    _description = "Mẫu tài liệu cho thuê"
    _inherit = ["mc.group.mixin"]
    _order = "company_id, template_type, is_default desc, id desc"

    name = fields.Char(string="Tên mẫu", required=True)
    company_id = fields.Many2one(
        "res.company",
        string="Công ty",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    template_type = fields.Selection(
        selection=[
            ("contract_docx", "Hợp đồng thuê (DOCX)"),
            ("contract_quotation_xlsx", "Bảng báo giá vật tư (XLSX)"),
            ("transport_matrix_xlsx", "Bảng xác nhận khối lượng (XLSX)"),
            ("transport_import_xlsx", "Biểu mẫu import xuất nhập kho (XLSX)"),
            ("rental_invoice_xlsx", "Bảng thanh toán tiền thuê (XLSX)"),
            ("debt_confirmation_xlsx", "Bảng đối chiếu xác nhận công nợ (XLSX)"),
            ("equipment_receipt_xlsx", "Phiếu giao nhận thiết bị (XLSX)"),
        ],
        string="Loại mẫu",
        required=True,
        index=True,
    )
    template_usage = fields.Char(
        string="Dùng khi",
        compute="_compute_template_usage",
        help="Nút / thao tác trên hệ thống sẽ dùng mẫu này (theo công ty).",
    )
    file_data = fields.Binary(
        string="File mẫu",
        required=True,
        attachment=True,
        help="Tải lên file Word (.docx) hoặc Excel (.xlsx). "
             "Nếu không upload, hệ thống dùng file mẫu mặc định đi kèm module.",
    )
    file_name = fields.Char(string="Tên file gốc")
    is_default = fields.Boolean(
        string="Mặc định cho loại này",
        help="Cùng công ty và loại mẫu: chỉ nên có một bản ghi được đánh dấu mặc định. "
             "Khi tải file, hệ thống ưu tiên bản mặc định.",
    )
    data_start_row = fields.Integer(
        string="Dòng bắt đầu dữ liệu",
        default=13,
        help="Chỉ dùng cho Bảng thanh toán tiền thuê (XLSX). "
             "Dòng Excel đầu tiên ghi dòng tính tiền (cột B–I); header thường ở dòng liền trước. "
             "Mẫu mặc định module: 13. Mẫu có dòng xác nhận + header riêng: thường 15.",
    )
    active = fields.Boolean(default=True)

    _DATA_START_ROW_DEFAULT = 13

    @api.depends("template_type")
    def _compute_template_usage(self):
        usage_map = {
            "contract_docx": "In / tải hợp đồng thuê (DOCX, PDF)",
            "contract_quotation_xlsx": "Tải bảng báo giá trên hợp đồng",
            "transport_matrix_xlsx": "Bảng xác nhận khối lượng — Download Excel",
            "transport_import_xlsx": "Import xuất nhập kho — nút Tải biểu mẫu",
            "rental_invoice_xlsx": "Bảng thanh toán — Xuất KLCT + HSTT / Tải bảng thanh toán chi tiết",
            "debt_confirmation_xlsx": "Xuất bảng đối chiếu xác nhận công nợ",
            "equipment_receipt_xlsx": "Tải phiếu giao nhận thiết bị (phiếu vận chuyển)",
        }
        for rec in self:
            rec.template_usage = usage_map.get(rec.template_type, "")

    @api.constrains("file_data")
    def _check_file_present(self):
        for rec in self:
            if not rec.file_data:
                raise ValidationError(_("Bạn phải tải lên file mẫu."))

    @api.constrains("data_start_row", "template_type")
    def _check_data_start_row(self):
        for rec in self:
            if rec.template_type != "rental_invoice_xlsx":
                continue
            if not rec.data_start_row or rec.data_start_row < 2:
                raise ValidationError(
                    _("Dòng bắt đầu dữ liệu phải là số nguyên ≥ 2 (thường 13 hoặc 15).")
                )

    @api.constrains("is_default", "company_id", "template_type", "active")
    def _check_single_default_per_type(self):
        for rec in self.filtered(lambda r: r.is_default and r.active):
            dup = self.search(
                [
                    ("company_id", "=", rec.company_id.id),
                    ("template_type", "=", rec.template_type),
                    ("is_default", "=", True),
                    ("active", "=", True),
                    ("id", "!=", rec.id),
                ],
                limit=1,
            )
            if dup:
                raise ValidationError(
                    _(
                        "Đã có mẫu mặc định cho loại «%(type)s» tại công ty %(company)s: %(name)s.",
                        type=dict(rec._fields["template_type"].selection).get(rec.template_type),
                        company=rec.company_id.display_name,
                        name=dup.name,
                    )
                )

    @api.model
    def _resolve_active_template(self, company, template_type):
        """Mẫu đã upload phù hợp nhất cho company + loại mẫu.

        Ưu tiên giảm dần để LUÔN ưu tiên mẫu đã upload hơn file mặc định trong module:
        1. Đúng công ty của bản ghi.
        2. Cùng nhóm công ty (company_group).
        3. Bất kỳ mẫu nào (toàn hệ thống) cùng loại — tránh trường hợp upload mẫu ở công ty
           này nhưng hợp đồng lại thuộc công ty khác → rơi nhầm về file mặc định module.
        """
        if not company or not template_type:
            return self.browse()
        base_domain = [
            ("template_type", "=", template_type),
            ("active", "=", True),
        ]
        order = "is_default desc, id desc"
        # 1) Đúng công ty
        template = self.search(
            base_domain + [("company_id", "=", company.id)], order=order, limit=1
        )
        if template:
            return template
        # 2) Cùng nhóm công ty
        group = company.company_group_id
        if group:
            template = self.search(
                base_domain + [("company_group_id", "=", group.id)], order=order, limit=1
            )
            if template:
                return template
        # 3) Bất kỳ mẫu đã upload cùng loại
        return self.search(base_domain, order=order, limit=1)

    @api.model
    def get_template_bytes(self, company, template_type):
        """
        File bytes for export/print: company upload first, else module static file.
        Returns (data, source) with source in ('upload', 'static').
        """
        template = self._resolve_active_template(company, template_type)
        if template and template.file_data:
            return base64.b64decode(template.file_data), "upload"

        default_filename = TEMPLATE_DEFAULT_FILES.get(template_type)
        if not default_filename:
            raise ValidationError(_("Unknown template type: %s") % template_type)

        template_path = get_module_resource(
            "rental",
            "static",
            "file_template",
            default_filename,
        )
        if not template_path:
            raise ValidationError(
                _(
                    "Chưa có mẫu «%(type)s» cho công ty %(company)s và không tìm thấy file mặc định %(fname)s.",
                    type=template_type,
                    company=company.display_name if company else "",
                    fname=default_filename,
                )
            )
        with open(template_path, "rb") as f:
            return f.read(), "static"

    @api.model
    def get_rental_invoice_xlsx(self, company):
        """Bytes + data start row for HSTT / bảng thanh toán XLSX.

        Returns (data, data_start_row). When no company upload exists, falls back to
        the module static file and the historic default row 13.
        """
        template = self._resolve_active_template(company, "rental_invoice_xlsx")
        data, _source = self.get_template_bytes(company, "rental_invoice_xlsx")
        start_row = template.data_start_row if template else self._DATA_START_ROW_DEFAULT
        if not start_row or start_row < 2:
            start_row = self._DATA_START_ROW_DEFAULT
        return data, start_row

    @api.model
    def get_template_stream(self, company, template_type):
        """File-like object for docxtpl / openpyxl loaders."""
        data, _source = self.get_template_bytes(company, template_type)
        return io.BytesIO(data)

    @api.model
    def get_template_path_or_stream(self, company, template_type):
        """
        Backward-compatible helper for DocxTemplate: stream if uploaded, else filesystem path.
        """
        template = self._resolve_active_template(company, template_type)
        if template and template.file_data:
            return self.get_template_stream(company, template_type)

        default_filename = TEMPLATE_DEFAULT_FILES.get(template_type)
        return get_module_resource("rental", "static", "file_template", default_filename)
