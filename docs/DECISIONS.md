# Spa Staff Payroll Decisions (ADR Lite)

Track architecture and implementation decisions so future agents keep consistency.

## Template
### [DEC-ID] Decision title
- Date:
- Status: proposed | accepted | superseded
- Context:
- Decision:
- Consequences:
- Alternatives considered:
- Related files/modules:

---

## Decisions

### [PAY-DEC-2026-07-26-15] Aggregated service_payout ledger + Buổi làm detail
- Date: 2026-07-26
- Status: accepted
- Context: Ledger liệt kê từng session làm rối tab Lương; cần tổng theo loại như HH.
- Decision: `service_payout_session` = **1 dòng tổng**; chi tiết trên `service_line_ids` (tab Buổi làm), rebuild cùng «Tính các khoản» với công thức profile. Long/requested bonus cũng 1 dòng / loại. Khóa sync flag booking→session qua `service.line` trên phiếu done (không còn source_id trên ledger buổi).
- Consequences: supersedes per-session ledger lines; PAY-DEC-05 SoT vẫn ledger aggregated.
- Alternatives considered: giữ N dòng ledger; model detail mới (thừa vì đã có service.line).
- Related files/modules: `spa_staff_payroll.py`, `spa_booking_payroll_fields.py`, views

### [PAY-DEC-2026-07-26-14] Form tab «Lương» tổng hợp; tab khác = chi tiết
- Date: 2026-07-26
- Status: accepted
- Context: Trùng smart button + tab HH/KPI; user muốn một chỗ xem tổng tiền phiếu.
- Decision: Tab đầu **Lương** chứa wage/prorate + tổng hợp (`amount_*`) + ledger `line_ids` (bỏ tab «Các khoản lương»). Tab HH/KPI/OT/Dịch vụ/Nghỉ chỉ drill-down. Bỏ smart button HH/KPI; giữ «Đặt lịch».
- Consequences: volume O2M load cùng form (chấp nhận cho quy mô tháng Spa).
- Alternatives considered: chỉ smart button (lazy hơn nếu không đặt O2M trên form); giữ header «Tổng hợp» ngoài notebook.
- Related files/modules: `views/spa_staff_payroll_views.xml`, `spa_staff_payroll.py`

### [PAY-DEC-2026-07-26-12] Wage prorate by contract overlap days
- Date: 2026-07-26
- Status: accepted
- Context: HĐ giữa tháng vẫn copy full `contract.wage` trong khi kỳ phiếu luôn ngày 1–cuối tháng.
- Decision: `_spa_prorate_contract_wage`: `wage_fixed = wage × days_worked / days_period` với overlap `max(date_from, date_start)`…`min(date_to, date_end)`; audit fields trên phiếu; gọi từ generate / onchange / Lấy từ HĐ. Ranking year slip vẫn `wage_fixed=0`.
- Consequences: NV vào giữa tháng nhận đúng phần lương cứng; dayoff vẫn không trừ tự động.
- Alternatives considered: chỉnh `date_from` theo HĐ (phá kỳ tháng / báo cáo).
- Related files/modules: `spa_staff_payroll.py`, `spa_staff_payroll_generate_wizard.py`

### [PAY-DEC-2026-07-26-13] Commission/KPI detail models + per-session shift bonus
- Date: 2026-07-26
- Status: accepted (shift bonus aggregation superseded by PAY-DEC-2026-07-26-15)
- Context: NV cần đối chiếu HH theo SP/đơn; ledger chỉ 1 dòng tổng.
- Decision: `spa.staff.payroll.commission.line` + `kpi.line` (tab chi tiết); ledger HH/KPI giữ 1 dòng = sum detail. (Thưởng ca: xem DEC-15 — 1 dòng / loại.)
- Consequences: recompute xóa/tạo lại detail; ACL + multi-company rule qua `payroll_id`.
- Alternatives considered: chỉ nhiều dòng ledger (thiếu cột SP/CK); chỉ smart button mở SO.
- Related files/modules: `spa_staff_payroll_detail_line.py`, `spa_staff_payroll.py`, views/security

### [PAY-DEC-2026-07-26-11] Sales commission / KPI when SO settled (residual = 0)
- Date: 2026-07-26
- Status: accepted
- Context: Đặt cọc tháng 5 / trả đủ tháng 7 — HH chỉ khi đơn thu đủ; base sau CK dòng; kỳ lương = tháng đủ tiền.
- Decision:
  - HH/KPI ghi nhận khi **SO settled**: `state` ∈ sale/done, `amount_to_invoice ≈ 0`, mọi HĐ posted gắn SO có `amount_residual ≈ 0`.
  - **Kỳ** = ngày đủ tiền (max ngày payment/reconcile làm residual = 0; fallback `invoice_date`) nằm trong kỳ phiếu.
  - Base HH = `sale.order.line.price_subtotal` (sau CK dòng) × `%` danh mục; bỏ dòng downpayment/`display_type`.
  - Fallback: HĐ không gắn SO → `payment_state=paid` + ngày đủ tiền trong kỳ; base `invoice_line.price_subtotal`.
  - Salesperson: SO `user_id` / HĐ `invoice_user_id`.
- Consequences: depend `sale`; KPI đồng bộ cùng cash-basis; ranking doanh số cùng rule.
- Alternatives considered: chỉ `invoice_date` + paid trên HĐ (lệch case cọc/trả sau).
- Related files/modules: `models/spa_staff_payroll.py`, `wizards/spa_payroll_ranking_wizard.py`

### [PAY-DEC-2026-07-26-10] Default tiers seeded global via XML noupdate
- Date: 2026-07-26
- Status: accepted
- Context: Menu KPI/ca dài trống nếu chưa chạy wizard; cần data mặc định theo spec, user sửa được sau.
- Decision: Seed XML `noupdate` với `company_id` trống (mọi công ty); `_spa_ensure_default_tiers` / wizard / `post_init_hook` idempotent cùng pattern global.
- Consequences: `-u` không ghi đè sửa tay; DB cũ nhận seed khi upgrade lần đầu có XML id.
- Alternatives considered: chỉ wizard; seed gắn `env.company`.
- Related files/modules: `data/spa_payroll_default_tiers_data.xml`, `models/payroll_config.py`

### [PAY-DEC-2026-07-26-01] Custom payslip model instead of Enterprise hr_payroll
- Date: 2026-07-26
- Status: accepted (existing; documented from code/README)
- Context: cần phiếu lương Spa trên Odoo Community; `hr_payroll` thường thuộc Enterprise.
- Decision: dùng model riêng `spa.staff.payroll` (+ line/service/OT) phụ thuộc `hr` + `hr_contract` cho employee/wage/OT rate; không depend `hr_payroll`.
- Consequences: workflow/state/report tự quản; không tương thích payslip chuẩn Odoo; agent không giả định salary structure/rules của Enterprise.
- Alternatives considered: `hr_payroll` Enterprise; tích hợp bên thứ ba.
- Related files/modules: `models/spa_staff_payroll.py`, `README.md`, `__manifest__.py`

### [PAY-DEC-2026-07-26-02] Ledger lines as audit trail for auto + manual amounts
- Date: 2026-07-26
- Status: accepted (existing)
- Context: cần kiểm tra từng khoản (tiền công buổi, thưởng ca, KPI, hoa hồng, ăn trưa, điều chỉnh tay).
- Decision: ledger `spa.staff.payroll.line` với `category`, `is_manual`, `source_model`/`source_id` (hiển thị trên tab «Lương»); recompute chỉ xóa/ghi dòng auto theo category; dòng manual giữ lại.
- Consequences: tổng `amount_payroll_lines` = sum mọi dòng ledger; category `service_payout_session` nằm trong ledger (không chỉ tab Dịch vụ).
- Alternatives considered: chỉ field Monetary trên header; chỉ tab Dịch vụ legacy.
- Related files/modules: `models/spa_staff_payroll_adjust_line.py`, `action_recompute_payroll_extras`

### [PAY-DEC-2026-07-26-03] Payroll math from treatment sessions, not bookings
- Date: 2026-07-26
- Status: accepted (existing)
- Context: booking_calendar là UI lịch; buổi làm thực tế / trạng thái done nằm ở `spa.treatment.session`.
- Decision: domain tính lương (service payout, shift bonuses, lunch) theo session `state=done` + `date` trong kỳ + `therapist_ids`; booking chỉ hỗ trợ UX (calendar filter, flags UI, màu).
- Consequences: phụ thuộc đúng gắn therapist trên session; flags trên booking không đủ nếu không có trên session (PAY-BUG-2026-07-26-02).
- Alternatives considered: tính từ `spa.service.booking` state=done (`_spa_booking_domain_in_period` tồn tại nhưng không dùng).
- Related files/modules: `models/spa_staff_payroll.py`, `spa` treatment session

### [PAY-DEC-2026-07-26-04] Service product payout by staff level profile
- Date: 2026-07-26
- Status: accepted (existing)
- Context: khác cấp NV (`spa.staff.level`) trả khác nhau cho cùng dịch vụ.
- Decision: `spa.product.payroll.profile` + payout lines; fallback `service_employee_salary`.
- Consequences: cần `spa_staff_level_id`; % qua `_spa_price_per_session`.
- Related files/modules: `models/product_payroll.py`

### [PAY-DEC-2026-07-26-05] Ledger SoT + multi-therapist split equal
- Date: 2026-07-26
- Status: accepted (detail storage updated by PAY-DEC-2026-07-26-15)
- Decision: `service_payout_session` là SoT (1 dòng tổng); `amount_service` không vào tổng; payout full rồi `/ len(therapist_ids)`; chi tiết session trên `service_line_ids`.
- Related: `spa_staff_payroll.py`, wizard generate

### [PAY-DEC-2026-07-26-06] Ranking via result + period close (not per-payslip recompute)
- Date: 2026-07-26
- Status: accepted
- Decision: `spa.payroll.ranking.result` + wizard chốt kỳ; `need_review` khi hòa; năm → phiếu kỳ năm riêng; seed năm amount=0.
- Related: `spa_payroll_ranking.py`, wizards

### [PAY-DEC-2026-07-26-07] Seniority display only (exclude long leave ≥28 days)
- Date: 2026-07-26
- Status: accepted
- Decision: compute/display trên employee + phiếu; không cộng tiền.
- Related: `hr_employee_seniority.py`
