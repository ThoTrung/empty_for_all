import inspect

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class CreateInvoiceWizard(models.TransientModel):
    _name = "create.invoice.wizard"

    start_date = fields.Date(string='Từ ngày')
    end_date = fields.Date(string='Đến ngày')
    transport_fee_until_date = fields.Date(
        string='Tính phí vận chuyển đến ngày',
        help='Lấy phí VC chưa tính của phiếu có ngày bắt đầu tính tiền ≤ ngày này. '
             'Trống = không tính phí vận chuyển kỳ này.',
    )

    _ALLOWED_CALLBACKS = {
        'rental.contract': {
            'action_export_transport_matrix_excel',
            'action_create_transport_matrix_record',
            'action_export_invoice_excel',
            'action_export_klct_hstt_excel',
            # 'action_create_rental_invoice',
            'export_debt_confirmation_comparison_table',
        },
        # Add more models/methods that accept (start_date, end_date)
        # 'your.model': {'your_method'},
    }

    @api.onchange('end_date')
    def _onchange_end_date_transport_fee_until(self):
        if self.end_date and not self.transport_fee_until_date:
            self.transport_fee_until_date = self.end_date

    def _get_target_records_and_method(self):
        """Resolve records and the callback method from context safely."""
        self.ensure_one()
        ctx = self.env.context or {}

        active_model = ctx.get('active_model')
        active_ids = ctx.get('active_ids') or []
        method_name = ctx.get('date_range_callback')
        if not active_model or not active_ids or not method_name:
            raise UserError(_("Wizard thiếu context: 'active_model', 'active_ids', hoặc 'date_range_callback'."))
        # Security: enforce whitelist
        allowed = self._ALLOWED_CALLBACKS.get(active_model, set())
        if method_name not in allowed:
            raise UserError(_(
                "Phương thức '%(method)s' không được phép với model %(model)s.",
                method=method_name, model=active_model
            ))

        recs = self.env[active_model].browse(active_ids).exists()
        if not recs:
            raise UserError(_("Không tìm thấy bản ghi hợp lệ."))

        # Ensure the callback exists
        if not hasattr(recs, method_name):
            raise UserError(_("Không tìm thấy phương thức '%s' trên %s.") % (method_name, active_model))

        return recs, method_name

    def choose_invoice_date_range(self):
        """Main entry: call the target method with (start_date, end_date)."""
        self.ensure_one()
        if self.end_date < self.start_date:
            raise UserError(_("Ngày kết thúc phải sau hoặc bằng ngày bắt đầu."))

        recs, method_name = self._get_target_records_and_method()

        # Call on each record (so per-record side effects/messages are handled)

        for rec in recs:
            method = getattr(rec, method_name)
            kwargs = {}
            try:
                params = inspect.signature(method).parameters
            except (TypeError, ValueError):
                params = {}
            if 'transport_fee_until_date' in params:
                kwargs['transport_fee_until_date'] = self.transport_fee_until_date
            action = method(self.start_date, self.end_date, **kwargs)
            if action.get("type") == "ir.actions.act_url":
                action = {**action, "target": "new"}
                url = action.get("url")
                return {
                    "type": "ir.actions.client",
                    "tag": "download_and_close",
                    "params": {"url": url},
                }
            # If callback opens a new window/form, just return it (wizard will close).
            if action.get("type") in ("ir.actions.act_window", "ir.actions.client"):
                return action
