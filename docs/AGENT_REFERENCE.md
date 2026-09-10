# Spa Staff Payroll Module Reference (Living Doc)

> **Phiên làm việc chuẩn:** Áp dụng `docs/AGENT_SESSION_DEFAULTS.md` cho cụm `spa` / `booking_calendar` / `spa_staff_payroll`.

> Hướng dẫn thao tác: `README.md`. Bậc mặc định (KPI/ca dài/khách đặt/giải) seed XML `noupdate` khi cài/upgrade (`company_id` trống). Wizard **Nạp bậc lương mặc định** vẫn idempotent.

## 1) Business Scope
- Phiếu lương Spa Community: lương cứng, tiền công buổi (profile theo cấp), OT, thưởng ca dài/khách đặt, KPI, hoa hồng SP, ăn trưa, thưởng xếp hạng tháng/năm, thâm niên (hiển thị).
- Không dùng Enterprise `hr_payroll`.

## 2) Technical Scope
- Core: `spa.staff.payroll` + ledger `spa.staff.payroll.line` + OT/dayoff lines.
- Config: lunch (`lunch_min_minutes`), long/requested/KPI tiers, `spa.payroll.ranking.prize` / `.result`.
- Ranking wizard: `spa.payroll.ranking.compute.wizard`; load tiers: `spa.payroll.load.default.tiers.wizard`.
- Seniority: `hr.employee` fields `spa_work_start_date`, `spa_seniority_*`.
- Report QWeb: `spa_staff_payroll.report_spa_staff_payroll_document`.
- Sync: booking flags → session (`spa_treatment_session_payroll_fields` + booking write).

## 3) Data Model Notes
- State: `draft` → `to_approve` → `done` | `cancel`.
- **SoT tiền công buổi = ledger `service_payout_session` (1 dòng tổng)**; chi tiết từng session trên tab **Buổi làm** (`service_line_ids`). `amount_service` không cộng vào `amount_total_payable`.
- Tổng: `wage_fixed + amount_overtime + amount_payroll_lines + amount_bonus − insurance − other`.
- **`wage_fixed` prorate** theo overlap HĐ ∩ kỳ: `wage × days_worked / days_period`; audit `wage_period_*` / `wage_days*`.
- Categories ledger thêm `ranking_bonus`. Thưởng ca dài / khách đặt: **1 dòng tổng / loại**.
- Chi tiết audit: `commission_line_ids` (HH theo SP), `kpi_line_ids` (theo SO/HĐ), `service_line_ids` (buổi); ledger HH/KPI/tiền công vẫn **1 dòng tổng** = sum detail.
- KPI base: field `kpi_revenue_base` (audit). **Không** đọc `spa.dashboard.month.line` (snapshot Dashboard cache-only).
- Dayoff / thâm niên: display; nghỉ dài ≥28 ngày trừ khỏi thâm niên.
- `spa.product.payroll.profile.company_id` **optional** (trống = mọi công ty); domain trên SP: `| company_id=False | company_id=product.company_id`.
- Hoa hồng bán: `%` trên `product.category` (+ walk parent); field SP `spa_sales_commission_percent` legacy ẩn UI.
- HH/KPI: SO settled; KPI/ranking = `_spa_recognized_amount_total` (net CK, trừ cọc) (PAY-DEC-2026-08-29-01). HH skip dòng CK toàn đơn. Eligibility `spa_settled_date` không đòi `spa_is_settled` (PAY-DEC-2026-08-28-01). CN gắn SO paid trong kỳ → clawback; phiếu `done` → activity.

## 4) View Architecture
- Phiếu: sheet = định danh (NV/HĐ/kỳ); tab **Lương** = wage + tổng hợp tiền + ledger `line_ids` (1 dòng / loại); tab chi tiết = Hoa hồng SP, KPI, OT, **Buổi làm**, Ngày nghỉ. Smart button chỉ «Đặt lịch». PDF report binding.
- Menu: Chốt xếp hạng kỳ, Kết quả xếp hạng, Đối soát ca, Giải thưởng, Nạp bậc mặc định.
- Session form: hiện flag payroll (readonly nếu từ booking).
- Booking form operator (**Lịch phục vụ**): flag ca/khách đặt readonly (`view_spa_staff_payroll_inherit_booking_form_operator`).
- Employee HR Settings: thâm niên Spa.
- Product template form: group `group_spa_payroll_profile` (Payroll Spa) **trước** `group_spa_composite_service`; bảng payout 50% cột trái (`colspan="2"`), help dưới bảng.

## 5) Security Model
- Groups payroll user/manager (Spa Manager imply manager).
- Record rules: overtime own/manager; **multi-company** trên payroll + lines.
- ACL cho ranking prize/result + wizards.

## 6) Main Workflows
1. HĐ + user → wizard tháng → Tính các khoản + OT → Gửi duyệt → Xác nhận.
2. Sau cài/upgrade đã có bậc global; wizard nạp lại nếu thiếu (idempotent).
3. Ranking: cấu hình prize → Chốt xếp hạng kỳ → sửa `need_review` nếu hòa → Chốt & đẩy ledger. Năm tạo phiếu kỳ 01/01–31/12 (wage 0).
4. Flag ca dài/khách đặt trên booking; sync session; không sync nếu session đã trên phiếu `done`.

## 7) Dependencies
`spa`, `booking_calendar`, `sale`, `account`, `hr`, `hr_contract`, `mail`.

## 8) Tests
```bash
python3 odoo/odoo-bin -c conf/odoo_dev.conf -d drlai \
  -u spa_staff_payroll --test-enable --test-tags=/spa_staff_payroll \
  --stop-after-init --http-port=8090
```
Cover: no double-count service, multi-therapist split, booking→session sync, seniority, load tiers, workflow to_approve, legacy OT/service/colors.
Commission/KPI cash-basis: category % walk; HĐ lẻ paid-date; SO May→July settle; partial pay=0; multi-% lines; KPI month; wrong salesperson; not invoiced; no SO/HĐ double-count; ranking sales; pct=0; late refund clawback T7/T9; activity on done refund-month slip.
Wage prorate mid-month start/end; commission/KPI detail sum = ledger; long-shift 1 line/session.

## 9) Known Pitfalls
- Flag vẫn phụ thuộc thao tác người — dùng menu Đối soát ca.
- KPI theo ngày đủ tiền / SO settled **net CK trừ cọc** (`_spa_recognized_amount_total`) — không theo `invoice_date` / không `amount_total` (có dòng cọc).
- Seed năm ranking amount = 0 đến khi QL nhập.
- Tier/prize mặc định: XML `noupdate` + `company_id` trống; user sửa không bị reset khi `-u`.

## 10) Change Protocol
Đọc memory quartet; giữ SoT ledger; ranking chỉ qua result/chốt kỳ; cập nhật test + WORKLOG.
