# Worklog (giữ ~3 entry mới; cũ hơn xoá bớt)

## 2026-07-20 — HSTT data_start_row theo mẫu công ty

files: `models/rental_template.py`, `views/rental_template_view.xml`, `models/rental_contract.py`, `tests/test_klct_hstt_combined_export.py`, `__manifest__.py` 17.0.1.0.48
why: Mỗi công ty có layout bảng thanh toán khác (data từ dòng 13 hoặc 15). Hardcode gây MergedCell khi mẫu mới merge dòng xác nhận A13:I13. Thêm setting «Dòng bắt đầu dữ liệu» (default 13) trên `rental.template`.
validation: test default row 13 + case `data_start_row=15` không ghi đè merge.

## 2026-07-17 — Giới hạn KH tra cứu theo công ty

files: `wizard/rental_rented_qty_wizard.py`, `tests/test_rented_qty_as_of.py`, `__manifest__.py` 17.0.1.0.47
why: Dropdown tra cứu SL đang thuê trước đây chỉ lọc `is_company`, nên hiện cả My Company, công ty thường và đối tác thuộc công ty Odoo khác. Nay chỉ nhận công ty có `customer_type = renter` và `company_id` đúng công ty hiện tại, kèm constraint server.
validation: focused as-of/wizard tests và module upgrade pass.

## 2026-07-17 — Tra cứu SL khách hàng đang thuê theo ngày

files: `services/rental_contract_services.py`, `wizard/rental_rented_qty_wizard.py`, `wizard/rental_rented_qty_wizard.xml`, `tests/test_rented_qty_as_of.py`, security/views, `__manifest__.py` 17.0.1.0.46
why: Nhân viên cần tra cứu số lượng tính tiền, chuyển thừa và tổng vật lý tại KH ở cuối một ngày; kết quả dùng đúng engine LIFO/HSTT và chỉ lấy phiếu vận chuyển đã hoàn tất.
validation: 7 test as-of pass; regression billing và KLCT+HSTT pass; module upgrade và XML load thành công.
