# Worklog (giữ ~3 entry mới; cũ hơn xoá bớt)

## 2026-07-25 — Fix DomainSelector Tài xế (verified on DB rental)

files: `static/src/js/domain_selector_field_domain.js`, `models/res_partner.py` name_search context, tests, `__manifest__.py` 17.0.1.0.71
why: DB chứng minh name_search([]) = mọi partner; DomainSelector không truyền domain. Vá RecordAutocomplete.getDomain theo label «Tài xế» + fallback path + TreeEditor.
validation: `TestPartnerCompanyIsolation`; hard-refresh; custom filter Tài xế chỉ còn driver.

## 2026-07-25 — Thống kê: Tồn kho + Xuất nhập tồn

files: stock XNT / analytics, `__manifest__.py` 17.0.1.0.68–70, DEC-27
why: Tồn kho as-of + XNT kỳ cạnh on-hire.
validation: `TestStockXnt`.

## 2026-07-25 — Partner domain trong search / custom filter

files: domain_selector patch, M2O domains, `__manifest__.py` 17.0.1.0.67
why: DomainSelector bỏ field.domain; siết driver/renter.
validation: `TestPartnerCompanyIsolation`.
