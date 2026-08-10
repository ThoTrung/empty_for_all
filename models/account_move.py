import base64
import calendar

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = "account.move"

    rental_contract_id = fields.Many2one(
        "rental.contract",
        string="Hợp đồng thuê",
        index=True,
        ondelete="set null",
        tracking=True,
        help="Hợp đồng mà hóa đơn này thuộc về.",
    )
    rental_partner_company_id = fields.Many2one(
        related="rental_contract_id.a_company_party",
        string="Khách hàng thuê",
        store=True,
        index=True,
        domain="[('is_rental_customer', '=', True), ('is_company', '=', True)]",
    )
    rental_construction_work_id = fields.Many2one(
        related="rental_contract_id.construction_work_id",
        string="Gói thầu / Công trình",
        store=True,
        index=True,
    )
    rental_start_date = fields.Date(string="Ngày bắt đầu hóa đơn")
    rental_end_date = fields.Date(string="Ngày kết thúc hóa đơn")
    transport_fee_until_date = fields.Date(
        string="Tính phí vận chuyển đến ngày",
        help="Cutoff phí VC đã dùng khi tạo hóa đơn này (audit).",
        copy=False,
    )
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
        string='File nghiệp vụ XLSX',
        copy=False,
    )

    def _rental_release_transport_fees(self):
        """Clear fee_billed_* on transports that pointed at these invoices."""
        Transport = self.env["rr.transport"]
        for move in self:
            transports = Transport.search([("fee_invoice_id", "=", move.id)])
            if transports:
                transports.write({
                    "fee_billed_date": False,
                    "fee_invoice_id": False,
                })

    def unlink(self):
        # Draft/posted rental invoices must be cancelled first (releases fee_billed_*).
        blocked = self.filtered(
            lambda m: m.rental_contract_id and m.state != "cancel"
        )
        if blocked:
            raise UserError(
                _(
                    "Không được xóa hóa đơn thuê khi chưa hủy. Hãy hủy hóa đơn trước "
                    "để thu hồi phí vận chuyển, rồi mới xóa."
                )
            )
        rental_cancelled = self.filtered(
            lambda m: m.rental_contract_id and m.state == "cancel"
        )
        if rental_cancelled:
            rental_cancelled._rental_release_transport_fees()
        return super().unlink()

    def button_cancel(self):
        rental = self.filtered("rental_contract_id")
        res = super().button_cancel()
        rental._rental_release_transport_fees()
        return res

    def button_draft(self):
        rental = self.filtered("rental_contract_id")
        res = super().button_draft()
        rental._rental_release_transport_fees()
        return res

    def action_download_business_xlsx(self):
        """Download the existing KLCT+HSTT attachment (no rebuild).

        Sheet ĐCCN may be stale after payments — use «Tạo lại» to refresh.
        """
        self.ensure_one()
        att = self.business_xlsx_attachment_id
        if not att:
            raise UserError(
                _(
                    "Chưa có file bảng thanh toán. Hãy tạo hóa đơn thuê với kỳ ngày trước."
                )
            )
        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{att.id}?download=1",
            "target": "self",
        }

    def action_regenerate_business_xlsx(self):
        """Rebuild KLCT+HSTT(+ĐCCN) from current data/templates, then download."""
        self.ensure_one()
        if not (
            self.rental_contract_id
            and self.rental_start_date
            and self.rental_end_date
        ):
            raise UserError(
                _(
                    "Chỉ tạo lại được với hóa đơn thuê đã gắn hợp đồng và kỳ ngày."
                )
            )
        buffer, _subtotal = self.rental_contract_id._build_klct_hstt_xlsx_buffer(
            self.rental_start_date,
            self.rental_end_date,
            fee_invoice=self,
        )
        contract = self.rental_contract_id
        filename = (
            f"KLCT-HSTT {self.rental_end_date.strftime('%m-%Y')} - {contract.code}.xlsx"
        )
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
                _("Chỉ tải được với hóa đơn thuê đã gắn hợp đồng và kỳ ngày.")
            )
        buffer = self.rental_contract_id._build_rental_payment_xlsx_buffer(
            self.rental_start_date,
            self.rental_end_date,
            fee_invoice=self,
        )
        contract = self.rental_contract_id
        filename = f"HSTT {self.rental_end_date.strftime('%m-%Y')} - {contract.code}"
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
        "rental_contract_id.monthly_day_basis",
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
                if c.monthly_day_basis == "fixed_30":
                    move.rental_billing_explanation = (
                        "Hợp đồng tính theo THÁNG (cơ sở 30 ngày cố định): đơn giá một ngày trên bảng thanh toán = "
                        "(giá bán tháng trên biến thể × tỷ lệ đơn giá so với báo giá trên HĐ) ÷ 30 ngày. "
                        "Thành tiền dòng hóa đơn = đơn giá × số ngày thuê × khối lượng (theo vận chuyển trong kỳ)."
                    )
                elif end:
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
