# Worklog (giữ ~3 entry mới; cũ hơn xoá bớt)

## 2026-07-20 — HSTT placeholders contract_number / contract_date

files: `models/rental_contract.py`, `tests/test_klct_hstt_combined_export.py`
why: Mẫu bảng thanh toán cần in số HĐ và ngày HĐ. Thêm `{{contract_number}}` và `{{contract_date}}` (format giống báo giá) vào `_rental_invoice_xlsx_apply_placeholders`.
validation: unit test replace placeholder trên sheet HSTT.

## 2026-07-20 — HSTT data_start_row theo mẫu công ty

files: `models/rental_template.py`, `views/rental_template_view.xml`, `models/rental_contract.py`, `tests/test_klct_hstt_combined_export.py`, `__manifest__.py` 17.0.1.0.48
why: Mỗi công ty có layout bảng thanh toán khác (data từ dòng 13 hoặc 15). Hardcode gây MergedCell khi mẫu mới merge dòng xác nhận A13:I13. Thêm setting «Dòng bắt đầu dữ liệu» (default 13) trên `rental.template`.
validation: test default row 13 + case `data_start_row=15` không ghi đè merge.

## 2026-07-17 — Giới hạn KH tra cứu theo công ty

files: `wizard/rental_rented_qty_wizard.py`, `tests/test_rented_qty_as_of.py`, `__manifest__.py` 17.0.1.0.47
why: Dropdown tra cứu SL đang thuê trước đây chỉ lọc `is_company`, nên hiện cả My Company, công ty thường và đối tác thuộc công ty Odoo khác. Nay chỉ nhận công ty có `customer_type = renter` và `company_id` đúng công ty hiện tại, kèm constraint server.
validation: focused as-of/wizard tests và module upgrade pass.
