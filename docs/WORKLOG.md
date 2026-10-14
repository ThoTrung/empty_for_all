# Worklog (giữ ~3 entry mới; cũ hơn xoá bớt)

## 2026-10-08 — Modal phiếu trong tab HĐ: Lưu & đóng / Lưu & tạo mới lưu luôn HĐ

files: `static/src/js/transport_one2many_field.js` (widget `rental_transport_one2many`), `views/rental_contract_view.xml`, `__manifest__.py` (assets)
why: X2ManyFieldDialog chỉ đưa phiếu vào list tạm của HĐ → NV phải lưu HĐ thêm lần nữa. Widget bọc saveRecord/updateRecord để gọi `record.save()` của HĐ ngay sau đó; lưu lỗi thì HĐ vẫn dirty.
validation: UI thủ công; `-u rental` nạp view/asset trên bản sao DB

## 2026-10-08 — Tạo phiếu từ tab HĐ lỗi "sequence item 0: expected str instance, bool found"

files: `models/transport.py` (`TransportLine._compute_display_name`), `tests/test_transport_one_picking.py`; `__manifest__` 17.0.1.0.88
why: Bỏ footer dialog → phiếu mới lưu qua `rental.contract.web_save` → tracking `rr_transport_line_ids` join `display_name` của dòng; `name` dòng luôn rỗng → False → TypeError. display_name dòng = "<mã phiếu> - <vật tư>".
validation: `test_create_transport_from_contract_tracks_existing_lines`, `test_line_display_name_falls_back_to_transport_and_product`

## 2026-10-08 — Phiếu giao nhận: Hoàn thành 1 bước, Nhân bản mở modal, list tab cập nhật

files: `models/transport.py` (`action_complete_transport`, `_rental_stock_shortages`, `_rental_check_before_picking`, `_rental_action_reload_and_open`, `action_duplicate_transport`, `copy_data`), `wizard/rr_transport_complete_wizard.*`, `static/src/js/transport_reload_open.js`, `views/transport_view.xml` (bỏ footer + nút Phiếu kho), `views/rental_contract_view.xml`, `controllers/rental_transport_controller.py`, `security/*`; `rental_subrent` hook kiểm lô; `__manifest__` 17.0.1.0.87 (subrent 17.0.1.0.8)
why: Footer `special="save"` trong dialog One2many ghi DB nhưng list HĐ không biết → phải F5. "Tạo phiếu kho" + xác nhận tách 2 bước. Hoàn thành chặn khi đã có phiếu kho mở (luồng cũ) để NV tự xử lý; thiếu tồn → wizard, đồng ý thì xuất âm.
validation: `TestTransportOnePicking` (duplicate + complete_*), `rental_subrent` lifecycle; chạy trên bản sao DB `rental`

## 2026-10-01 — HSTT: 1 dịch vụ "Tổng thanh toán" dùng chung, không tạo mới mỗi tháng

files: `models/rental_contract.py` (`_get_or_create_hstt_total_product`, `_create_rental_invoice_from_hstt_total`), `tests/test_klct_hstt_combined_export.py`, `migrations/17.0.1.0.86/post-migrate.py`; `__manifest__` 17.0.1.0.86
why: Tên product cũ gắn kỳ ("Tổng thanh toán: MM-YYYY") nên search-or-create không bao giờ khớp tháng trước → mỗi tháng sinh 1 product rác. Tên product nay cố định, kỳ chuyển sang mô tả dòng hoá đơn (`account.move.line.name`); migration archive product trùng lặp cũ, hoá đơn cũ giữ nguyên `product_id`.
validation: `test_hstt_total_invoice_reuses_single_product_across_periods`, `test_hstt_total_product_replaces_stale_tax_with_eight_percent`

## 2026-08-10 — KLCT+HSTT: UserError khi không có chuyến done

files: `models/rental_contract.py`, `helper/transport_matrix_export.py`, `tests/test_klct_hstt_combined_export.py`; `__manifest__` 17.0.1.0.84
why: RC00038 tháng 7 chỉ có draft → `groups_meta` rỗng → `merge_cells(4,3)` crash openpyxl. Guard sớm + message NV nhắc hoàn thành phiếu.
validation: `test_draft_only_transports_raise_user_error_not_merge_crash`

## 2026-08-04 — HSTT MD qty SoT = KLCT Tổng MD

files: `services/rental_contract_services.py` (pool present rebuild); tests KLCT+HSTT + billing cross-variant; `__manifest__` 17.0.1.0.82
why: Trả cross-variant (vd 2m trừ lô 3m) để phantom present → HSTT BOB ≠ KLCT → mất F→Tổng MD. Present sau pool = mét còn mở (= KLCT); HĐ vẫn lấy `round(HSTT subtotal)`.
validation: `test_pooled_cross_variant_*`, `test_md_cross_variant_return_bob_refs_klct_tong_md_and_invoice_matches`; shell INV/2026/00006 Hộp 5*5 BOB=438 F→KLCT
