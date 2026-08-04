# Worklog (giữ ~3 entry mới; cũ hơn xoá bớt)

## 2026-08-01 — Pause UX NCC: đọc STATUS rồi quyết

files: `rental_subrent/docs/STATUS_NCC_UX.md` + DECISIONS open backlog
why: Phase 0–2 (A1+B1) xong; tạm dừng — backlog: ẩn create menu, tracked UI, unify `rr.transport`, hóa đơn NCC, DEBT-04/05.
validation: docs; versions `rental` 17.0.1.0.81 · `rental_subrent` 17.0.1.0.7

## 2026-08-01 — Phase 2: embed Nhập/Trả trên HĐ NCC

files: `rental_subrent` O2M receipt/return + tab + tests DEC-S12; `__manifest__` 17.0.1.0.7
why: A1 — tạo/xem nhận-trả từ HĐ; menu list giữ; stock/policy không đổi.
validation: `-u rental_subrent --test-tags=subrent_contract_moves`

## 2026-08-01 — Phase 1: form HĐ NCC (meta + đại diện)

files: `rental_subrent` contract fields/view/tests DEC-S11; `__manifest__` subrent 17.0.1.0.6
why: B1 parity tối thiểu — ngày/số HĐ giấy, đại diện NCC/ta, notebook Thông tin + SP/giá.
validation: `-u rental_subrent --test-tags=subrent_contract_form`
