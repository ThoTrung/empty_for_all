# Worklog

## 2026-08-01 — Pause: document hiện trạng A1+B1

files: `docs/STATUS_NCC_UX.md` (shipped Phase 0–2 + backlog quyết định), `docs/DECISIONS.md` (open list)
why: tạm dừng UX NCC; đọc STATUS rồi chọn hướng tiếp (menu-only / tracked / unify VC / invoice / DEBT-04/05).
validation: n/a — docs only; versions ổn định `rental` 17.0.1.0.81 · `rental_subrent` 17.0.1.0.7

## 2026-08-01 — Phase 2: embed Nhập/Trả trên HĐ NCC

files: `models/rental_subrent_contract.py` (`receipt_ids`/`return_ids`), form tab `subrent_moves`, help menu Nhận/Trả, `tests/test_subrent_contract_moves.py`, DEC-S12, USER_GUIDE §4.1/4.4; `__manifest__` 17.0.1.0.7
why: mental model VC — tạo nhận/trả từ HĐ; menu list giữ; không đổi stock/policy.
validation: `-u rental_subrent --test-tags=subrent_contract_moves`

## 2026-08-01 — Phase 1: làm giàu form HĐ NCC (B1)

files: `models/rental_subrent_contract.py` (contract_date/number, reps), `views/rental_subrent_contract_view.xml` (notebook Thông tin + SP/giá), `tests/test_subrent_contract_form.py`, DEC-S11, USER_GUIDE §3; `__manifest__` 17.0.1.0.6
why: form HĐ NCC sơ sài; parity tối thiểu với HĐ khách (meta + đại diện), chưa embed Nhận/Trả.
validation: `-u rental_subrent --test-tags=subrent_contract_form`
