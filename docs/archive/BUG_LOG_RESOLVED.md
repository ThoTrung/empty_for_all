# Resolved bugs

### BUG-2026-06-04-01 — Matrix HTML columns overlap
- Fix: `table-layout: auto; width: max-content` in `rental_transport_matrix.py`

### BUG-2026-06-04-02 — Missing Tổng MD column
- Fix: `_group_needs_md_column()` for single variant length products

### BUG-2026-06-04-03 — Excel matrix last column format
- Fix: `extend_product_column_styles()` in `export_excel_template.py`

### BUG-2026-06-04-04 — Payment table amount in words wrong
- Fix: `{{total_after_tax_string}}` placeholder + `_rental_invoice_xlsx_apply_payment_totals()`
