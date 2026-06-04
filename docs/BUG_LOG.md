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

_(Cập nhật khi fix được merge.)_
