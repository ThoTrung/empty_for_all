import base64
import calendar

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = "account.move"

    rental_contract_id = fields.Many2one(
        "rental.contract",
        string="Rental Contract",
        index=True,
        ondelete="set null",
        tracking=True,
        help="Contract this invoice belongs to.",
    )
    rental_start_date = fields.Date(string="Invoice start date")
    rental_end_date = fields.Date(string="Invoice end date")
    rental_billing_mode = fields.Selection(
        related="rental_contract_id.rental_billing_mode",
        string="Cách tính tiền thuê (HĐ)",
        readonly=True,
    )
    rental_billing_explanation = fields.Text(
        string="Giải thích cách tính",
        compute="_compute_rental_billing_explanation",
    )
    business_xlsx_attachment_id = fields.Many2one(
        'ir.attachment',
        string='Business XLSX',
        copy=False,
    )

    def action_download_business_xlsx(self):
        """Regenerate payment table from current company template, then download."""
        self.ensure_one()
        if not (
            self.rental_contract_id
            and self.rental_start_date
            and self.rental_end_date
        ):
            att = self.business_xlsx_attachment_id
            if not att:
                raise UserError(
                    _(
                        "No payment table file. Create a rental invoice with period dates first."
                    )
                )
            return {
                "type": "ir.actions.act_url",
                "url": f"/web/content/{att.id}?download=1",
                "target": "self",
            }
        buffer = self.rental_contract_id._build_rental_payment_xlsx_buffer(
            self.rental_start_date,
            self.rental_end_date,
        )
        contract = self.rental_contract_id
        filename = f"BẢNG THANH TOÁN KHỐI LƯỢNG VÀ GIÁ TRỊ THUÊ {contract.code}.xlsx"
        if self.business_xlsx_attachment_id:
            self.business_xlsx_attachment_id.write(
                {
                    "name": filename,
                    "datas": base64.b64encode(buffer.getvalue()),
                    "mimetype": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                }
            )
            att = self.business_xlsx_attachment_id
        else:
            att = self.env["ir.attachment"].create(
                {
                    "name": filename,
                    "res_model": "account.move",
                    "res_id": self.id,
                    "type": "binary",
                    "datas": base64.b64encode(buffer.getvalue()),
                    "mimetype": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                }
            )
            self.business_xlsx_attachment_id = att.id
        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{att.id}?download=1",
            "target": "self",
        }

    def action_download_rental_payment_table_grouped(self):
        """Tải bảng thanh toán gộp theo mẫu SP (cùng logic file Business XLSX / xuất từ HĐ)."""
        self.ensure_one()
        if not (self.rental_contract_id and self.rental_start_date and self.rental_end_date):
            raise UserError(
                _("This download is only available for rental invoices with contract and period dates.")
            )
        buffer = self.rental_contract_id._build_rental_payment_xlsx_buffer(
            self.rental_start_date,
            self.rental_end_date,
        )
        contract = self.rental_contract_id
        filename = f"BẢNG THANH TOÁN KHỐI LƯỢNG VÀ GIÁ TRỊ THUÊ {contract.code}"
        attachment = self.env["ir.attachment"].create(
            {
                "name": f"{filename}.xlsx",
                "res_model": "account.move",
                "res_id": self.id,
                "type": "binary",
                "datas": base64.b64encode(buffer.getvalue()),
                "mimetype": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            }
        )
        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{attachment.id}?download=1",
            "target": "self",
        }

    @api.depends(
        "rental_contract_id",
        "rental_contract_id.rental_billing_mode",
        "rental_end_date",
    )
    def _compute_rental_billing_explanation(self):
        for move in self:
            if not move.rental_contract_id:
                move.rental_billing_explanation = False
                continue
            c = move.rental_contract_id
            end = move.rental_end_date
            if c.rental_billing_mode == "month":
                if end:
                    dim = calendar.monthrange(end.year, end.month)[1]
                    move.rental_billing_explanation = (
                        "Hợp đồng tính theo THÁNG: đơn giá một ngày trên bảng thanh toán = "
                        "(giá bán tháng trên biến thể × tỷ lệ đơn giá so với báo giá trên HĐ) "
                        f"÷ {dim} ngày của tháng {end.month:02d}/{end.year}. "
                        "Thành tiền dòng hóa đơn = đơn giá × số ngày thuê × khối lượng (theo vận chuyển trong kỳ)."
                    )
                else:
                    move.rental_billing_explanation = (
                        "Hợp đồng tính theo THÁNG: đơn giá ngày được quy từ giá tháng ÷ số ngày trong tháng của kỳ hóa đơn."
                    )
            else:
                move.rental_billing_explanation = (
                    "Hợp đồng tính theo NGÀY: đơn giá một ngày = Giá thuê/ngày trên sản phẩm × tỷ lệ đơn giá trên HĐ. "
                    "Nếu chưa nhập giá thuê/ngày, hệ thống quy đổi từ giá tháng (như chế độ theo tháng)."
                )


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    staff_display_uom_id = fields.Many2one(
        "uom.uom",
        string="Đơn vị hiển thị",
        compute="_compute_staff_display_uom_id",
    )
    rental_price_month = fields.Monetary(
        string="Giá tháng (biến thể)",
        compute="_compute_rental_price_display",
        currency_field="currency_id",
        help="Giá bán tháng (lst_price) trên product.product của dòng hóa đơn.",
    )
    rental_price_day = fields.Monetary(
        string="Giá ngày (biến thể)",
        compute="_compute_rental_price_display",
        currency_field="currency_id",
        help="Giá thuê theo ngày (rental_price_day) trên product.product của dòng hóa đơn.",
    )

    @api.depends(
        "move_id.rental_contract_id",
        "product_id",
        "product_id.lst_price",
        "product_id.rental_price_day",
        "display_type",
        "currency_id",
    )
    def _compute_rental_price_display(self):
        """Giá tháng / ngày hiển thị theo biến thể (product.product), không lấy từ product.template."""
        for line in self:
            if (
                line.display_type in ("line_section", "line_note")
                or not line.product_id
                or not line.move_id.rental_contract_id
            ):
                line.rental_price_month = 0.0
                line.rental_price_day = 0.0
                continue
            p = line.product_id
            line.rental_price_month = p.lst_price
            line.rental_price_day = p.rental_price_day or 0.0

    @api.depends(
        "display_type",
        "product_id",
        "product_id.staff_display_uom_id",
        "product_id.uom_id",
    )
    def _compute_staff_display_uom_id(self):
        for line in self:
            if line.display_type in ("line_section", "line_note") or not line.product_id:
                line.staff_display_uom_id = False
            else:
                line.staff_display_uom_id = line.product_id._get_staff_display_uom()
