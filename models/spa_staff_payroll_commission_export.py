# -*- coding: utf-8 -*-

import base64
import io
import re
import unicodedata
from collections import OrderedDict

import xlsxwriter

from odoo import _, fields, models
from odoo.exceptions import AccessError, UserError


class SpaStaffPayroll(models.Model):
    _inherit = "spa.staff.payroll"

    # ------------------------------------------------------------------
    # Xuất Excel hoa hồng SP gộp các chi nhánh (company) của cùng 1 người.
    # Một người làm ở 2 chi nhánh = 2 hr.employee chung 1 res.users → 2 phiếu
    # (mỗi company 1 phiếu). Gộp theo user_id + cùng kỳ. PAY-DEC-2026-09-25-02.
    # ------------------------------------------------------------------

    def _spa_merged_commission_groups(self):
        """Trả về list dict {key, name, date_from, date_to, payslips, hidden_count}.

        Tìm phiếu anh em (cùng user, cùng kỳ, chưa hủy) trong các công ty user
        đang đăng nhập được phép (không sudo → record rule vẫn áp dụng).
        """
        allowed = self.env.user.company_ids
        Payroll = self.with_context(allowed_company_ids=allowed.ids).env["spa.staff.payroll"]
        groups = OrderedDict()
        for rec in self.sorted(lambda r: (r.employee_id.name or "", r.date_from, r.id)):
            if rec.user_id:
                key = ("user", rec.user_id.id, rec.date_from, rec.date_to)
            else:
                key = ("employee", rec.employee_id.id, rec.date_from, rec.date_to)
            if key in groups:
                continue
            if rec.user_id:
                sibling_domain = [
                    ("user_id", "=", rec.user_id.id),
                    ("date_from", "=", rec.date_from),
                    ("date_to", "=", rec.date_to),
                    ("state", "!=", "cancel"),
                ]
                payslips = Payroll.search(sibling_domain, order="company_id, id")
                # Chỉ đếm (không đọc dữ liệu) phiếu ở chi nhánh user không có quyền.
                hidden_count = self.env["spa.staff.payroll"].sudo().search_count(
                    sibling_domain + [("company_id", "not in", allowed.ids)]
                )
            else:
                payslips = rec
                hidden_count = 0
            if rec.state != "cancel":
                payslips = (payslips | rec).sorted(lambda p: (p.company_id.id, p.id))
            groups[key] = {
                "name": rec.employee_id.name or rec.user_id.name or "",
                "date_from": rec.date_from,
                "date_to": rec.date_to,
                "payslips": payslips,
                "hidden_count": hidden_count,
            }
        return list(groups.values())

    def action_export_commission_xlsx_merged(self):
        if not self.env.user.has_group("spa_staff_payroll.group_spa_payroll_manager"):
            raise AccessError(_("Chỉ quản lý lương mới được xuất Excel hoa hồng."))
        if not self:
            raise UserError(_("Chọn ít nhất 1 phiếu lương."))
        groups = self._spa_merged_commission_groups()
        file_bytes = self._spa_build_commission_merged_xlsx(groups)
        if len(groups) == 1:
            g = groups[0]
            slug = re.sub(r"[^0-9A-Za-z]+", "_", _spa_ascii(g["name"])).strip("_") or "nv"
            file_name = "hoa_hong_%s_%s.xlsx" % (slug, g["date_from"].strftime("%Y%m"))
        else:
            file_name = "hoa_hong_gop_chi_nhanh_%s.xlsx" % fields.Date.context_today(self).strftime("%Y%m%d")
        export = self.env["spa.staff.payroll.commission.export"].create({
            "file_name": file_name,
            "file_data": base64.b64encode(file_bytes),
        })
        return {
            "type": "ir.actions.act_window",
            "name": _("Xuất Excel hoa hồng (gộp chi nhánh)"),
            "res_model": "spa.staff.payroll.commission.export",
            "view_mode": "form",
            "res_id": export.id,
            "target": "new",
        }

    def _spa_build_commission_merged_xlsx(self, groups):
        """Trả về bytes file xlsx: mỗi nhóm (người + kỳ) 1 sheet."""
        output = io.BytesIO()
        wb = xlsxwriter.Workbook(output, {"in_memory": True})

        # Format theo locale Việt Nam (042A), giống _spa_build_daily_sale_export_xlsx.
        title_fmt = wb.add_format({"bold": True, "font_size": 14})
        bold_fmt = wb.add_format({"bold": True})
        warn_fmt = wb.add_format({"bold": True, "font_color": "#C00000"})
        header_fmt = wb.add_format({"bold": True, "bg_color": "#D9EAD3", "border": 1, "text_wrap": True, "valign": "vcenter"})
        text_fmt = wb.add_format({"border": 1})
        date_fmt = wb.add_format({"border": 1, "num_format": "dd/mm/yyyy"})
        money_fmt = wb.add_format({"border": 1, "num_format": "[$-042A]#,##0"})
        qty_fmt = wb.add_format({"border": 1, "num_format": "[$-042A]#,##0.##"})
        pct_fmt = wb.add_format({"border": 1, "num_format": "[$-042A]#,##0.##"})
        sub_text_fmt = wb.add_format({"border": 1, "bold": True, "bg_color": "#FFF2CC"})
        sub_money_fmt = wb.add_format({"border": 1, "bold": True, "bg_color": "#FFF2CC", "num_format": "[$-042A]#,##0"})
        total_text_fmt = wb.add_format({"border": 1, "bold": True, "bg_color": "#F4CCCC"})
        total_money_fmt = wb.add_format({"border": 1, "bold": True, "bg_color": "#F4CCCC", "num_format": "[$-042A]#,##0"})

        state_labels = dict(self._fields["state"].selection)
        branch_labels = {"clinic": "Phòng khám", "spa": "Spa"}
        used_names = set()

        if not groups:
            wb.add_worksheet("Trong")
        for g in groups:
            sheet = wb.add_worksheet(_spa_sheet_name(g["name"], used_names))
            payslips = g["payslips"]
            row = 0
            sheet.write(row, 0, "HOA HỒNG SẢN PHẨM — GỘP CHI NHÁNH", title_fmt)
            row += 1
            sheet.write(row, 0, "Nhân viên:", bold_fmt)
            sheet.write(row, 2, g["name"])
            row += 1
            sheet.write(row, 0, "Kỳ:", bold_fmt)
            sheet.write(row, 2, "%s - %s" % (
                g["date_from"].strftime("%d/%m/%Y"), g["date_to"].strftime("%d/%m/%Y")))
            row += 1
            currencies = payslips.currency_id
            sheet.write(row, 0, "Tiền tệ:", bold_fmt)
            sheet.write(row, 2, ", ".join(currencies.mapped("name")))
            row += 1
            if len(currencies) > 1:
                sheet.write(row, 0, "Cảnh báo: các phiếu khác tiền tệ — tổng cộng chỉ mang tính tham khảo.", warn_fmt)
                row += 1
            if g["hidden_count"]:
                sheet.write(row, 0, "Lưu ý: có %d phiếu ở chi nhánh bạn không có quyền — không có trong file này."
                            % g["hidden_count"], warn_fmt)
                row += 1

            # --- Danh sách phiếu gộp ---
            row += 1
            for col, h in enumerate(["Số phiếu", "Công ty/Chi nhánh", "Trạng thái"]):
                sheet.write(row, col, h, header_fmt)
            row += 1
            for slip in payslips:
                sheet.write(row, 0, slip.name or "", text_fmt)
                sheet.write(row, 1, slip.company_id.name or "", text_fmt)
                sheet.write(row, 2, state_labels.get(slip.state, slip.state or ""), text_fmt)
                row += 1

            # --- Tổng hợp hoa hồng theo chi nhánh ---
            row += 1
            sheet.write(row, 0, "Tổng hợp hoa hồng theo chi nhánh", bold_fmt)
            row += 1
            for col, h in enumerate(["Công ty/Chi nhánh", "Số phiếu", "HH SP Spa", "HH SP Phòng khám", "Tổng HH"]):
                sheet.write(row, col, h, header_fmt)
            row += 1
            grand = {"spa": 0.0, "clinic": 0.0}
            for slip in payslips:
                lines = slip.commission_line_ids
                spa_amt = sum(lines.filtered(lambda l: l.product_branch != "clinic").mapped("commission_amount"))
                clinic_amt = sum(lines.filtered(lambda l: l.product_branch == "clinic").mapped("commission_amount"))
                grand["spa"] += spa_amt
                grand["clinic"] += clinic_amt
                sheet.write(row, 0, slip.company_id.name or "", text_fmt)
                sheet.write(row, 1, slip.name or "", text_fmt)
                sheet.write_number(row, 2, spa_amt, money_fmt)
                sheet.write_number(row, 3, clinic_amt, money_fmt)
                sheet.write_number(row, 4, spa_amt + clinic_amt, money_fmt)
                row += 1
            sheet.write(row, 0, "Tổng cộng", total_text_fmt)
            sheet.write(row, 1, "", total_text_fmt)
            sheet.write_number(row, 2, grand["spa"], total_money_fmt)
            sheet.write_number(row, 3, grand["clinic"], total_money_fmt)
            sheet.write_number(row, 4, grand["spa"] + grand["clinic"], total_money_fmt)
            row += 1

            # --- Chi tiết hoa hồng theo sản phẩm ---
            row += 1
            sheet.write(row, 0, "Chi tiết hoa hồng theo sản phẩm", bold_fmt)
            row += 1
            headers = [
                "Công ty/Chi nhánh", "Loại SP", "Ngày", "Đơn hàng/Hóa đơn", "Mã KH",
                "Khách hàng", "Sản phẩm", "Danh mục", "SL", "Đơn giá", "CK (%)",
                "CK HĐ", "Thành tiền", "% HH", "Hoa hồng",
            ]
            for col, h in enumerate(headers):
                sheet.write(row, col, h, header_fmt)
            sheet.freeze_panes(row + 1, 0)
            row += 1
            grand_sub = grand_comm = 0.0
            for slip in payslips:
                lines = slip.commission_line_ids.sorted(
                    lambda l: (l.product_branch or "", l.settle_date or fields.Date.today(), l.id))
                if not lines:
                    continue
                sub_sub = sub_comm = 0.0
                for line in lines:
                    source = line.sale_order_id.name or line.move_id.name or ""
                    if line.sale_order_id and line.move_id:
                        source = "%s / %s" % (line.sale_order_id.name, line.move_id.name)
                    sheet.write(row, 0, slip.company_id.name or "", text_fmt)
                    sheet.write(row, 1, branch_labels.get(line.product_branch, ""), text_fmt)
                    if line.settle_date:
                        sheet.write_datetime(row, 2, fields.Datetime.to_datetime(line.settle_date), date_fmt)
                    else:
                        sheet.write(row, 2, "", text_fmt)
                    sheet.write(row, 3, source, text_fmt)
                    sheet.write(row, 4, line.partner_code or "", text_fmt)
                    sheet.write(row, 5, line.partner_id.name or "", text_fmt)
                    sheet.write(row, 6, line.product_id.display_name or "", text_fmt)
                    sheet.write(row, 7, line.categ_id.display_name or "", text_fmt)
                    sheet.write_number(row, 8, line.quantity or 0.0, qty_fmt)
                    sheet.write_number(row, 9, line.price_unit or 0.0, money_fmt)
                    sheet.write_number(row, 10, line.discount or 0.0, pct_fmt)
                    sheet.write_number(row, 11, line.order_discount_share or 0.0, money_fmt)
                    sheet.write_number(row, 12, line.price_subtotal or 0.0, money_fmt)
                    sheet.write_number(row, 13, line.commission_percent or 0.0, pct_fmt)
                    sheet.write_number(row, 14, line.commission_amount or 0.0, money_fmt)
                    sub_sub += line.price_subtotal or 0.0
                    sub_comm += line.commission_amount or 0.0
                    row += 1
                sheet.write(row, 0, "Cộng %s" % (slip.company_id.name or ""), sub_text_fmt)
                for col in range(1, 12):
                    sheet.write(row, col, "", sub_text_fmt)
                sheet.write_number(row, 12, sub_sub, sub_money_fmt)
                sheet.write(row, 13, "", sub_text_fmt)
                sheet.write_number(row, 14, sub_comm, sub_money_fmt)
                row += 1
                grand_sub += sub_sub
                grand_comm += sub_comm
            sheet.write(row, 0, "TỔNG CỘNG", total_text_fmt)
            for col in range(1, 12):
                sheet.write(row, col, "", total_text_fmt)
            sheet.write_number(row, 12, grand_sub, total_money_fmt)
            sheet.write(row, 13, "", total_text_fmt)
            sheet.write_number(row, 14, grand_comm, total_money_fmt)

            sheet.set_column(0, 0, 24)
            sheet.set_column(1, 1, 12)
            sheet.set_column(2, 2, 12)
            sheet.set_column(3, 3, 26)
            sheet.set_column(4, 4, 12)
            sheet.set_column(5, 7, 28)
            sheet.set_column(8, 8, 8)
            sheet.set_column(9, 12, 14)
            sheet.set_column(13, 13, 8)
            sheet.set_column(14, 14, 14)

        wb.close()
        return output.getvalue()


_SHEET_BAD_CHARS = re.compile(r"[\[\]:*?/\\]")


def _spa_ascii(text):
    text = (text or "").replace("đ", "d").replace("Đ", "D")
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")


def _spa_sheet_name(name, used):
    """Tên sheet hợp lệ Excel: ≤31 ký tự, không []:*?/\\, không trùng (không phân biệt hoa thường)."""
    base = _SHEET_BAD_CHARS.sub(" ", name or "").strip().strip("'") or "NV"
    base = base[:31]
    candidate = base
    n = 2
    while candidate.lower() in used:
        suffix = " (%d)" % n
        candidate = base[: 31 - len(suffix)] + suffix
        n += 1
    used.add(candidate.lower())
    return candidate


class SpaStaffPayrollCommissionExport(models.TransientModel):
    _name = "spa.staff.payroll.commission.export"
    _description = "Tải file Excel hoa hồng gộp chi nhánh"
    # TransientModel: không lưu file ra đĩa / ir.attachment; bản ghi được hệ thống dọn.

    file_name = fields.Char(string="Tên file", readonly=True)
    file_data = fields.Binary(string="File Excel", readonly=True)
