# -*- coding: utf-8 -*-
import base64
import io
from datetime import date

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import format_date

from odoo.addons.rental.services import rental_stock_xnt as stock_xnt

try:
    from openpyxl import Workbook
except ImportError:  # pragma: no cover
    Workbook = None


class RentalStockXntWizard(models.TransientModel):
    _name = "rental.stock.xnt.wizard"
    _description = "Xuất nhập tồn (kho)"

    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        readonly=True,
    )
    date_from = fields.Date(
        string="Từ ngày",
        required=True,
        default=lambda self: fields.Date.context_today(self).replace(day=1),
    )
    date_to = fields.Date(
        string="Đến ngày",
        required=True,
        default=fields.Date.context_today,
    )
    warehouse_ids = fields.Many2many(
        "stock.warehouse",
        string="Kho",
        domain="[('company_id', 'in', allowed_company_ids)]",
    )
    product_ids = fields.Many2many(
        "product.product",
        string="Sản phẩm",
        domain="[('type', '=', 'product')]",
    )
    line_ids = fields.One2many(
        "rental.stock.xnt.wizard.line",
        "wizard_id",
        string="Xuất nhập tồn",
        readonly=True,
    )
    excel_file = fields.Binary(string="Excel", readonly=True, attachment=False)
    excel_filename = fields.Char(readonly=True)

    @api.constrains("date_from", "date_to")
    def _check_dates(self):
        for wizard in self:
            if wizard.date_from and wizard.date_to and wizard.date_from > wizard.date_to:
                raise UserError(_("Từ ngày phải nhỏ hơn hoặc bằng Đến ngày."))

    def action_compute(self):
        self.ensure_one()
        self.line_ids.unlink()
        rows = stock_xnt.calc_xnt_lines(
            self.env,
            self.date_from,
            self.date_to,
            company_ids=self.env.companies.ids,
            warehouse_ids=self.warehouse_ids.ids or None,
            product_ids=self.product_ids.ids or None,
        )
        vals_list = []
        for row in rows:
            vals_list.append({
                "wizard_id": self.id,
                "product_id": row["product_id"],
                "product_tmpl_id": row["product_tmpl_id"],
                "uom_id": row["uom_id"],
                "uom_name": row["uom_name"],
                "opening_qty": row["opening_qty"],
                "in_qty": row["in_qty"],
                "out_qty": row["out_qty"],
                "closing_qty": row["closing_qty"],
            })
        if vals_list:
            self.env["rental.stock.xnt.wizard.line"].create(vals_list)
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_export_excel(self):
        self.ensure_one()
        if not self.line_ids:
            self.action_compute()
        if not self.line_ids:
            raise UserError(_("Không có dữ liệu Xuất nhập tồn trong kỳ đã chọn."))
        if Workbook is None:
            raise UserError(_("Thiếu thư viện openpyxl để xuất Excel."))

        wb = Workbook()
        ws = wb.active
        ws.title = "XNT"
        ws.append([
            _("Sản phẩm"),
            _("Biến thể"),
            _("ĐVT"),
            _("Dư đầu kỳ"),
            _("Nhập"),
            _("Xuất"),
            _("Tồn"),
        ])
        for line in self.line_ids:
            ws.append([
                line.product_tmpl_id.display_name,
                line.product_id.display_name,
                line.uom_name or (line.uom_id.display_name if line.uom_id else ""),
                line.opening_qty,
                line.in_qty,
                line.out_qty,
                line.closing_qty,
            ])
        buf = io.BytesIO()
        wb.save(buf)
        filename = "XNT_%s_%s.xlsx" % (
            format_date(self.env, self.date_from).replace("/", "-"),
            format_date(self.env, self.date_to).replace("/", "-"),
        )
        self.write({
            "excel_file": base64.b64encode(buf.getvalue()),
            "excel_filename": filename,
        })
        return {
            "type": "ir.actions.act_url",
            "url": "/web/content?model=%s&id=%s&field=excel_file&filename_field=excel_filename&download=true"
            % (self._name, self.id),
            "target": "self",
        }

    @api.model
    def action_open_wizard(self, date_from=None, date_to=None, warehouse_ids=None):
        """Open wizard prefilled from dashboard filters."""
        today = fields.Date.context_today(self)
        if not date_to:
            date_to = today
        if not date_from:
            date_from = date_to.replace(day=1) if isinstance(date_to, date) else today.replace(day=1)
        vals = {
            "date_from": date_from,
            "date_to": date_to,
        }
        wizard = self.create(vals)
        if warehouse_ids:
            wizard.warehouse_ids = [(6, 0, list(warehouse_ids))]
        wizard.action_compute()
        return {
            "type": "ir.actions.act_window",
            "name": _("Xuất nhập tồn"),
            "res_model": self._name,
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
            "context": dict(self.env.context),
        }


class RentalStockXntWizardLine(models.TransientModel):
    _name = "rental.stock.xnt.wizard.line"
    _description = "Xuất nhập tồn line"
    _order = "product_tmpl_id, product_id"

    wizard_id = fields.Many2one(
        "rental.stock.xnt.wizard",
        required=True,
        ondelete="cascade",
    )
    product_id = fields.Many2one("product.product", string="Biến thể", required=True)
    product_tmpl_id = fields.Many2one("product.template", string="Sản phẩm", required=True)
    uom_id = fields.Many2one("uom.uom", string="ĐVT")
    uom_name = fields.Char(string="ĐVT (text)")
    opening_qty = fields.Float(string="Dư đầu kỳ", digits="Product Unit of Measure")
    in_qty = fields.Float(string="Nhập", digits="Product Unit of Measure")
    out_qty = fields.Float(string="Xuất", digits="Product Unit of Measure")
    closing_qty = fields.Float(string="Tồn", digits="Product Unit of Measure")
