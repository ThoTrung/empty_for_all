# -*- coding: utf-8 -*-
import base64

from odoo import fields, models, _
from odoo.exceptions import UserError

from ..helper.import_transport_matrix import parse_transport_matrix_xlsx


class RentalTransportImportPreviewLine(models.TransientModel):
    _name = "rental.transport.import.preview.line"
    _description = "Transport import preview line"
    _order = "row_number"

    wizard_id = fields.Many2one("rental.transport.import.wizard", required=True, ondelete="cascade")
    row_number = fields.Integer(string="Dòng Excel", readonly=True)
    transport_date = fields.Date(string="Ngày", readonly=True)
    plate = fields.Char(string="Biển số", readonly=True)
    transport_type = fields.Selection(
        [("delivery", "Xuất"), ("return", "Nhập")],
        string="Loại",
        readonly=True,
    )
    line_count = fields.Integer(string="Số dòng SP", readonly=True)
    status = fields.Selection(
        [("ok", "OK"), ("error", "Lỗi")],
        string="Trạng thái",
        readonly=True,
    )
    message = fields.Text(string="Ghi chú", readonly=True)


class RentalTransportImportWizard(models.TransientModel):
    _name = "rental.transport.import.wizard"
    _description = "Import transports from Excel matrix"

    rental_contract_id = fields.Many2one(
        "rental.contract",
        string="Hợp đồng",
        required=True,
        readonly=True,
    )
    import_file = fields.Binary(string="File Excel", required=True)
    import_filename = fields.Char(string="Tên file")
    default_driver_id = fields.Many2one(
        "res.partner",
        string="Tài xế mặc định",
        domain="[('customer_type', '=', 'driver')]",
        required=True,
    )
    auto_create_truck = fields.Boolean(
        string="Tự tạo xe nếu chưa có",
        default=True,
    )
    validate_picking = fields.Boolean(
        string="Tạo và xác nhận phiếu kho ngay",
        default=True,
        help="Sau khi import, tự tạo stock picking và xác nhận. "
             "Nếu kho không đủ tồn, hệ thống vẫn xác nhận và cho phép tồn kho âm (phù hợp nhập dữ liệu cũ).",
    )
    state = fields.Selection(
        [("upload", "Tải file"), ("preview", "Xem trước"), ("done", "Hoàn tất")],
        default="upload",
        required=True,
    )
    preview_line_ids = fields.One2many(
        "rental.transport.import.preview.line",
        "wizard_id",
        string="Xem trước",
        readonly=True,
    )
    summary = fields.Text(string="Tóm tắt", readonly=True)
    product_mapping_summary = fields.Text(
        string="Lỗi mapping sản phẩm",
        readonly=True,
    )
    created_transport_ids = fields.Many2many(
        "rr.transport",
        string="Phiếu đã tạo",
        readonly=True,
    )

    def action_download_template(self):
        self.ensure_one()
        return self.rental_contract_id.action_download_transport_import_template()

    def _parse_uploaded_file(self):
        self.ensure_one()
        if not self.import_file:
            raise UserError(_("Vui lòng chọn file Excel."))
        return parse_transport_matrix_xlsx(
            base64.b64decode(self.import_file),
            self.env,
            contract=self.rental_contract_id,
        )

    def _build_product_mapping_summary(self, product_mapping_errors):
        if not product_mapping_errors:
            return ""
        blocks = []
        for idx, item in enumerate(product_mapping_errors, start=1):
            blocks.append(
                _("%(n)s) Cột %(col)s — «%(label)s»\n%(detail)s") % {
                    "n": idx,
                    "col": item["col_letter"],
                    "label": item["excel_label"],
                    "detail": item["detail"],
                }
            )
        return "\n\n".join(blocks)

    def action_parse_file(self):
        self.ensure_one()
        parsed = self._parse_uploaded_file()

        preview_commands = [(5, 0, 0)]
        ok_count = 0
        error_count = 0
        for row in parsed["rows"]:
            row_errors = list(row.get("errors") or [])
            status = "error" if row_errors else "ok"
            if status == "ok":
                ok_count += 1
            else:
                error_count += 1
            message_parts = []
            if row_errors:
                message_parts.extend(row_errors)
            if row.get("warnings"):
                message_parts.extend(row["warnings"])
            preview_commands.append((0, 0, {
                "row_number": row["row_number"],
                "transport_date": row["transport_date"],
                "plate": row["plate"],
                "transport_type": row["transport_type"],
                "line_count": len(row.get("lines") or []),
                "status": status,
                "message": "\n".join(message_parts) if message_parts else _("Sẵn sàng import"),
            }))

        warnings = list(parsed.get("warnings") or [])
        product_mapping_summary = self._build_product_mapping_summary(
            parsed.get("product_mapping_errors") or []
        )
        summary_lines = [
            _("Tổng dòng hợp lệ: %(total)s") % {"total": len(parsed["rows"])},
            _("OK: %(ok)s | Lỗi: %(err)s") % {"ok": ok_count, "err": error_count},
        ]
        if warnings:
            summary_lines.append(_("Cảnh báo: %(n)s") % {"n": len(warnings)})
        if product_mapping_summary:
            summary_lines.append(
                _("Có %(n)s cột sản phẩm không khớp — xem tab «Lỗi mapping sản phẩm».") % {
                    "n": len(parsed.get("product_mapping_errors") or []),
                }
            )

        self.write({
            "state": "preview",
            "preview_line_ids": preview_commands,
            "summary": "\n".join(summary_lines),
            "product_mapping_summary": product_mapping_summary,
        })
        return self._reopen_wizard()

    def action_import_transports(self):
        self.ensure_one()
        parsed = self._parse_uploaded_file()

        blocking = []
        for row in parsed["rows"]:
            blocking.extend(row.get("errors") or [])
        if blocking:
            raise UserError(
                _("Không thể import vì còn lỗi:\n%s") % "\n".join(blocking[:20])
            )

        valid_rows = [r for r in parsed["rows"] if r.get("lines")]
        if not valid_rows:
            raise UserError(_("Không có dòng vận chuyển hợp lệ để import."))

        Transport = self.env["rr.transport"]
        Truck = self.env["transport.truck"]
        created = Transport
        picking_errors = []

        for row in valid_rows:
            truck = self._resolve_truck(Truck, row["plate"])
            vehicle_start = fields.Datetime.to_datetime(row["transport_date"])
            transport = Transport.create({
                "rental_contract_id": self.rental_contract_id.id,
                "type": row["transport_type"],
                "start_rental_or_return_date": row["transport_date"],
                "driver_id": self.default_driver_id.id,
                "transport_truck_id": truck.id,
                "vehicle_start_time": vehicle_start,
                "transport_line_ids": [
                    (0, 0, {"product_id": pid, "qty": qty})
                    for pid, qty in row["lines"]
                ],
            })
            created |= transport
            if self.validate_picking:
                try:
                    picking = transport._rental_create_picking()
                    transport._rental_validate_picking(picking)
                except UserError as err:
                    picking_errors.append(
                        _("Dòng %(row)s (%(code)s): %(err)s") % {
                            "row": row["row_number"],
                            "code": transport.code,
                            "err": err.args[0] if err.args else str(err),
                        }
                    )
                except Exception as err:
                    picking_errors.append(
                        _("Dòng %(row)s (%(code)s): %(err)s") % {
                            "row": row["row_number"],
                            "code": transport.code,
                            "err": str(err),
                        }
                    )

        if picking_errors:
            raise UserError(
                _("Đã tạo phiếu vận chuyển nhưng xác nhận kho thất bại:\n%s") % "\n".join(picking_errors)
            )

        summary = _("Đã tạo %(n)s phiếu xuất nhập kho.") % {"n": len(created)}
        if self.validate_picking:
            summary += " " + _("Đã tạo và xác nhận phiếu kho.")

        self.write({
            "state": "done",
            "created_transport_ids": [(6, 0, created.ids)],
            "summary": summary,
        })
        return self._open_created_transports(created)

    def _resolve_truck(self, Truck, plate):
        plate_norm = (plate or "").strip()
        if not plate_norm:
            raise UserError(_("Thiếu biển số xe."))
        truck = Truck.search([("plate", "=ilike", plate_norm)], limit=1)
        if truck:
            return truck
        if not self.auto_create_truck:
            raise UserError(_("Không tìm thấy xe biển số '%s'.") % plate_norm)
        return Truck.create({
            "plate": plate_norm,
            "name": plate_norm,
            "company_id": self.rental_contract_id.company_id.id,
        })

    def _reopen_wizard(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def _open_created_transports(self, transports):
        action = self.env["ir.actions.actions"]._for_xml_id("rental.action_rr_transport")
        action = dict(action)
        action["domain"] = [("id", "in", transports.ids)]
        action["context"] = dict(self.env.context or {})
        return action
