# Rental Bug Log (Living Doc)

Use one section per bug. Keep entries short and reproducible.

## Template

### [BUG-ID] Short title

- Date:
- Reporter:
- Context (screen/model/action):
- Symptom:
- Reproduction steps:
- Root cause:
- Fix summary:
- Files changed:
- Test coverage:
- Regression risk:
- Follow-up TODO:

---

## Active Bugs

_(Chưa ghi nhận bug mở trong repo — bổ sung khi phát hiện trong phiên làm việc.)_

---

## Known Issues / Tech Debt (not yet filed as bugs)

### [RENTAL-DEBT-01] Manifest missing `account` and `mail`

- Context: `__manifest__.py` chỉ depends sale/stock; code tạo `account.move` và dùng `mail.thread` / `message_post`.
- Risk: Cài `-i rental` trên DB tối thiểu có thể fail hoặc thiếu menu/view account.
- Safe direction: Thêm `'account'`, `'mail'` vào `depends` sau khi xác nhận production đã có sẵn.

### [RENTAL-DEBT-02] `rental.invoice.line._compute_total_price` calls `write()` inside compute

- Context: `models/rental_invoice.py` — anti-pattern Odoo.
- Risk: Performance, recursion, unexpected triggers.
- Safe direction: Assign `rec.rental_days` / `rec.total_price` trực tiếp trong compute loop.

### [RENTAL-DEBT-03] HTTP controllers browse with `sudo()` without company check

- Context: `controllers/rental_contract_controller.py`, `rental_transport_controller.py`.
- Risk: IDOR nếu user biết `contract_id` / `matrix_id` của công ty khác.
- Safe direction: Sau `browse`, `ensure_one()` + kiểm tra `contract.company_id in env.companies` hoặc bỏ sudo dùng record rules.

---

## Resolved Bugs

### [RENTAL-BUG-2026-06-04-01] Bảng xác nhận khối lượng — cột header bị đè

- Date: 2026-06-04
- Context: Form `rental.transport.matrix`, HTML `matrix_html`
- Symptom: Nhiều cột sản phẩm thì header chữ xếp chồng, không đọc được.
- Root cause: `table-layout: fixed; width: 100%` ép toàn bộ bảng vào viewport.
- Fix summary: `table-layout: auto; width: max-content` + scroll ngang; bỏ `max-width` quá hẹp trên cột tên.
- Files changed: `models/rental_transport_matrix.py`

### [RENTAL-BUG-2026-06-04-02] Thiếu cột Tổng MD cho SP mét dài (1 biến thể)

- Date: 2026-06-04
- Context: Ma trận HTML + export Excel
- Symptom: SP một biến thể có chiều dài (vd. Hộp 5*10 1,5m) không có cột Tổng MD.
- Root cause: Chỉ nhóm ≥2 biến thể mới thêm Tổng MD.
- Fix summary: `_group_needs_md_column()` — thêm Tổng MD khi parse được chiều dài hoặc ĐVT hiển thị là Mét dài.
- Files changed: `models/rental_transport_matrix.py`, `controllers/rental_contract_controller.py`, tests

### [RENTAL-BUG-2026-06-04-03] Export Excel ma trận — cột cuối mất format

- Date: 2026-06-04
- Context: `download_rental_contract_transport_matrix_xlsx`
- Symptom: Sản phẩm vượt quá cột W trong template mất viền/màu header.
- Root cause: Template chỉ style sẵn D–W; code thêm cột không clone style.
- Fix summary: `extend_product_column_styles()` + mở rộng merge header row 14.
- Files changed: `helper/export_excel_template.py`, `controllers/rental_contract_controller.py`

### [RENTAL-BUG-2026-06-04-04] Bảng thanh toán — tiền bằng chữ sai

- Date: 2026-06-04
- Context: Nút "Tải bảng thanh toán chi tiết" / `_build_rental_payment_xlsx_buffer`
- Symptom: Số tổng đúng (công thức Excel) nhưng dòng bằng chữ là text mẫu cố định (171.825.392đ).
- Root cause: Cell A216 trong `rental_invoice_template.xlsx` hard-code text mẫu.
- Fix summary: Placeholder `{{total_after_tax_string}}` + `_rental_invoice_xlsx_apply_payment_totals()` tính từ dữ liệu bảng.
- Files changed: `models/rental_contract.py`, `static/file_template/rental_invoice_template.xlsx`
