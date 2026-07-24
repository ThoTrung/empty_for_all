# Worklog (giữ ~3 entry mới; cũ hơn xoá bớt)

## 2026-07-24 — UX Dashboard-first: bỏ menu Báo cáo

files: `views/menu.xml`, `static/src/analytics_dashboard/*`, `__manifest__.py` 17.0.1.0.58
why: Chỉ đi Dashboard → click chi tiết; wizard «Tra cứu theo ngày» thành nút phụ trên Dashboard.
validation: `-u rental`; navbar không còn Báo cáo / Tra cứu.

## 2026-07-24 — Dashboard menu đầu + Home Action staff

files: `views/menu.xml`, `models/res_users.py`, `migrations/17.0.1.0.57/post-migrate.py`, `__manifest__.py` 17.0.1.0.57
why: Dashboard đứng đầu app Rental; staff đăng nhập mở thẳng client action Dashboard (`action_id`).
validation: `-u rental`; login staff → Dashboard.

## 2026-07-24 — Analytics Hub harden (ĐVT, TTL, công nợ)

files: `models/rental_analytics_*.py`, OWL filters, cron, migration 55, tests, `__manifest__.py` 17.0.1.0.55
why: P0 cộng lẫn ĐVT + refresh TTL; filter KH-công trình; widget công nợ.
validation: `TestAnalyticsOnHire`.
