from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class RentalTemplate(models.Model):
    _name = "rental.template"
    _description = "Mẫu tài liệu cho thuê"
    _inherit = ["mc.group.mixin"]

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
            ("contract_docx", "Contract (DOCX)"),
            ("contract_quotation_xlsx", "Contract Quotation (XLSX)"),
            ("transport_matrix_xlsx", "Transport Matrix (XLSX)"),
            ("rental_invoice_xlsx", "Rental Invoice (XLSX)"),
            ("debt_confirmation_xlsx", "Debt Confirmation (XLSX)"),
            ("equipment_receipt_xlsx", "Equipment Delivery Receipt (XLSX)"),
        ],
        string="Loại mẫu",
        required=True,
        index=True,
    )
    file_data = fields.Binary(
        string="File mẫu",
        required=True,
        attachment=True,
        help="Upload file Word/Excel dùng làm mẫu.",
    )
    file_name = fields.Char(string="Tên file gốc")
    is_default = fields.Boolean(
        string="Mặc định cho loại này",
        help="If several templates exist for the same company and type, "
        "the default one will be chosen first.",
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        (
            "template_unique_per_file_company",
            "unique(company_id, template_type, is_default)",
            "Only one default template per company and type is allowed.",
        ),
    ]

    @api.constrains("file_data")
    def _check_file_present(self):
        for rec in self:
            if not rec.file_data:
                raise ValidationError(_("Bạn phải tải lên file mẫu."))

