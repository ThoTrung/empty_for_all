# Bug log

> Active bugs + tech debt. Resolved → xoá khỏi đây.

## Active

_(none)_

## Tech debt

- DEBT-01 — Manifest missing `account`,`mail` → add to `depends` after prod check
- DEBT-02 — `rental.invoice.line` compute uses `write()` → assign fields in compute
- DEBT-03 — Controllers `sudo()` without company check → validate `company_id in env.companies`
- DEBT-04 — Rename `res.partner.customer_type` → `rental_partner_kind` / `partner_form_mode` (DEC-29: field không còn nghĩa «loại khách»; label UI đã là «Kiểu form»)
- DEBT-05 — Giá NCC↔NCC: multi-role cho phép chọn partner vừa NCC vừa KH; chưa có pricelist / `rental_price_class` / rule giá riêng trên `rental.contract` (follow-up DEC-29)
- DEBT-06 — Backlog UX thuê ngoài sau A1+B1 (chưa chọn): ẩn create menu Nhận/Trả; UI tracked/pass_through; unify → `rr.transport`; hóa đơn AP NCC — xem `rental_subrent/docs/STATUS_NCC_UX.md`

**New bug:** 1 dòng vào Active hoặc Tech debt; resolved → xoá.
