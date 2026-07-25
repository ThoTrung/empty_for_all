# Worklog (giữ ~3 entry mới; cũ hơn xoá bớt)

## 2026-07-25 — Partner domain trong search / custom filter

files: `static/src/js/domain_selector_field_domain.js`, `models/transport.py`, `models/rental_contract.py`, `models/rental_analytics_on_hire.py`, `models/account_move.py`, wizard import, search views, `tests/test_partner_company_isolation.py`, `__manifest__.py` 17.0.1.0.67
why: DomainSelector bỏ `field.domain` → suggest mọi res.partner; siết domain driver/renter + company; patch inject domain.
validation: `TestPartnerCompanyIsolation`; hard-refresh; custom filter Tài xế chỉ còn driver cty hiện tại.

## 2026-07-25 — Page title + Excel SUM phí VC

files: migration 17.0.1.0.66, `models/transport.py` `export_data`, `tests/test_transport_fee_export.py`, `__manifest__.py` 17.0.1.0.66
why: vi_VN action còn «Xuất nhập kho»; dòng tổng Excel dùng `=SUM(...)` thay số cứng.
validation: `TestTransportFeeExport`; `-u rental`; check title + formula trong XLSX.

## 2026-07-25 — Thống kê filter: many2many tags

files: `static/src/analytics_dashboard/*`, `__manifest__.py` 17.0.1.0.65
why: Filter KH/công trình dùng `MultiRecordSelector` (tags + autocomplete) thay Ctrl/Cmd `<select multiple>`.
validation: hard-refresh Thống kê; chọn/xóa tag → widget reload.
