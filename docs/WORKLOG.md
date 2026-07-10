# Worklog (giữ ~3 entry mới; cũ hơn xoá bớt)

## 2026-06-29 — Khớp trả/phạt gộp mét dài cho mẫu nhiều biến thể

files: `services/rental_contract_services.py` (`_build_billing_line_dict`, `_apply_pooled_returns_by_template`, `_pooled_return_lines_for_template`), `tests/test_rental_billing_scenarios.py`, `docs/DECISIONS.md` (DEC-09)
why: HĐ RC00083 tháng 8 — phần "Hộp 5*10 trả thuê từ 10/07 phạt 2 tháng" ra 1.696 do khớp LIFO theo TỪNG biến thể (cây 3m lô 10/07 chỉ 504, trả 964 → 460 dồn về lô 29/04 không phạt). Đổi sang POOL mét dài gộp toàn mẫu → toàn bộ phần trả dồn về lô giao mới nhất, ra 3.076 phạt (đúng kỳ vọng KH). Phần "đang thuê" giữ nguyên khớp theo biến thể.
validation: diagnostic RC00083 (T7 3.562 / T8 3.076 phạt) + 26/26 test billing pass (clone DB rental_test). 1 fail có sẵn `test_build_import_template_bytes` (không liên quan).

## 2026-06-05 — Import: picking option + biểu mẫu + lỗi SP chi tiết

`import_transport_matrix.py`, `transport.py`, `rental_transport_import_wizard.*`, `rental_contract.py`, `rental_contract_controller.py`, `test_transport_import.py`

## 2026-06-05 — Import transport từ Excel ma trận

Wizard tab Transports; col C biển số; qty âm=nhập; trùng ngày+plate trong file=lỗi. `helper/import_transport_matrix.py`, wizard, contract view, ACL.

---

### Template (entry mới)

```
## YYYY-MM-DD — Title
files: ...
validation: ...
```
