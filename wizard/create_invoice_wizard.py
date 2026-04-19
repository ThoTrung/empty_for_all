from odoo import api, fields, models, _
from odoo.exceptions import UserError


class CreateInvoiceWizard(models.TransientModel):
    _name = "create.invoice.wizard"

    start_date = fields.Date(string='Start date')
    end_date = fields.Date(string='End date')

    _ALLOWED_CALLBACKS = {
        'rental.contract': {
            'action_export_transport_matrix_excel',
            'action_create_transport_matrix_record',
            'action_export_invoice_excel',
            # 'action_create_rental_invoice',
            'export_debt_confirmation_comparison_table',
        },
        # Add more models/methods that accept (start_date, end_date)
        # 'your.model': {'your_method'},
    }

    def _get_target_records_and_method(self):
        """Resolve records and the callback method from context safely."""
        self.ensure_one()
        ctx = self.env.context or {}

        active_model = ctx.get('active_model')
        active_ids = ctx.get('active_ids') or []
        method_name = ctx.get('date_range_callback')
        if not active_model or not active_ids or not method_name:
            raise UserError(_("Wizard is missing context: 'active_model', 'active_ids', or 'date_range_callback'."))
        # Security: enforce whitelist
        allowed = self._ALLOWED_CALLBACKS.get(active_model, set())
        if method_name not in allowed:
            raise UserError(_(
                "Method '%(method)s' is not allowed for model %(model)s.",
                method=method_name, model=active_model
            ))

        recs = self.env[active_model].browse(active_ids).exists()
        if not recs:
            raise UserError(_("No valid records found."))

        # Ensure the callback exists
        if not hasattr(recs, method_name):
            raise UserError(_("Method '%s' not found on %s.") % (method_name, active_model))

        return recs, method_name

    def choose_invoice_date_range(self):
        """Main entry: call the target method with (start_date, end_date)."""
        self.ensure_one()
        if self.end_date < self.start_date:
            raise UserError(_("End date must be on or after Start date."))

        recs, method_name = self._get_target_records_and_method()

        # Call on each record (so per-record side effects/messages are handled)

        for rec in recs:
            action = getattr(rec, method_name)(self.start_date, self.end_date)
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
