# Worklog (giữ ~3 entry mới; cũ hơn xoá bớt)

## 2026-08-10 — KLCT+HSTT: UserError khi không có chuyến done

files: `models/rental_contract.py`, `helper/transport_matrix_export.py`, `tests/test_klct_hstt_combined_export.py`; `__manifest__` 17.0.1.0.84
why: RC00038 tháng 7 chỉ có draft → `groups_meta` rỗng → `merge_cells(4,3)` crash openpyxl. Guard sớm + message NV nhắc hoàn thành phiếu.
validation: `test_draft_only_transports_raise_user_error_not_merge_crash`

## 2026-08-04 — HSTT MD qty SoT = KLCT Tổng MD

files: `services/rental_contract_services.py` (pool present rebuild); tests KLCT+HSTT + billing cross-variant; `__manifest__` 17.0.1.0.82
why: Trả cross-variant (vd 2m trừ lô 3m) để phantom present → HSTT BOB ≠ KLCT → mất F→Tổng MD. Present sau pool = mét còn mở (= KLCT); HĐ vẫn lấy `round(HSTT subtotal)`.
validation: `test_pooled_cross_variant_*`, `test_md_cross_variant_return_bob_refs_klct_tong_md_and_invoice_matches`; shell INV/2026/00006 Hộp 5*5 BOB=438 F→KLCT

## 2026-08-01 — Pause UX NCC: đọc STATUS rồi quyết

files: `rental_subrent/docs/STATUS_NCC_UX.md` + DECISIONS open backlog
why: Phase 0–2 (A1+B1) xong; tạm dừng — backlog: ẩn create menu, tracked UI, unify `rr.transport`, hóa đơn NCC, DEBT-04/05.
validation: docs; versions `rental` 17.0.1.0.81 · `rental_subrent` 17.0.1.0.7
