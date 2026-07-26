# Spa Staff Payroll Worklog (Session Handoff)

Use this file for short session-level handoff notes.

## Template
### YYYY-MM-DD - Session title
- Goal:
- Changes made:
- Files touched:
- Validation done:
- Dependency impact check:
  - Dependents reviewed:
  - Contract compatibility result:
  - Regression tests/manual checks run:
- Open risks:
- Next suggested steps:

---

## Entries

### 2026-07-26 - Aggregate service ledger + tab Buổi làm
- Goal: Ledger 1 dòng tiền công buổi; chi tiết session trên tab Buổi làm; gộp thưởng ca theo loại.
- Changes made: `_spa_compute_session_service_payout_lines` tạo detail + 1 ledger; long/req 1 dòng; lock sync qua `service.line`; rename tab; tests.
- Files touched: `spa_staff_payroll.py`, `spa_booking_payroll_fields.py`, views, tests, docs, generate wizard comment
- Validation done: `--test-tags=/spa_staff_payroll` trên `drlai` — **0 failed, 0 error(s) of 32 tests**.
- Dependency impact check:
  - Dependents reviewed: booking flag lock; tests session/shift; form tab order.
  - Contract compatibility result: ledger vẫn category `service_payout_session` (số dòng giảm); detail bắt buộc qua service.line.
  - Regression tests/manual checks run: module suite.
- Open risks: phiếu done cũ khóa sync qua source_id ledger — session mới sau upgrade dùng service.line.
- Next suggested steps: UAT «Tính các khoản» trên phiếu nhiều buổi.

### 2026-07-26 - Form payroll label/layout polish
- Goal: Label 1 dòng; ẩn Công ty/Tiền tệ; Cộng ledger + Tổng phải trả cột trái; bỏ separator ledger.
- Changes made: override `string=` trên form; `company_id`/`currency_id` invisible; layout tab Lương; xóa separator.
- Files touched: `views/spa_staff_payroll_views.xml`, `docs/WORKLOG.md`
- Validation done: reload form phiếu (dev=reload).
- Dependency impact check:
  - Dependents reviewed: form view only; tree/report giữ string model.
  - Contract compatibility result: chỉ UI.
  - Regression tests/manual checks run: manual form check.
- Open risks: không.
- Next suggested steps: không.

### 2026-07-26 - UX tab Lương + bỏ smart button HH/KPI
- Goal: Tab «Lương» = wage + tổng hợp + ledger; tab khác = chi tiết; bỏ smart HH/KPI.
- Changes made: form sheet chỉ định danh; page `salary_summary`; xóa page `payroll_lines` + stat buttons; xóa count/actions Python; docs DEC-14.
- Files touched: `views/spa_staff_payroll_views.xml`, `models/spa_staff_payroll.py`, AGENT_REFERENCE, DECISIONS, WORKLOG, README
- Validation done: view-only UX; logic không đổi (tests suite không phụ thuộc smart button).
- Dependency impact check:
  - Dependents reviewed: form payroll; help text tab HH/KPI/OT/service/dayoff; README thao tác.
  - Contract compatibility result: chỉ UI; model/recompute giữ.
  - Regression tests/manual checks run: không bắt buộc full suite cho view-only; reload form trên `drlai`.
- Open risks: không.
- Next suggested steps: UAT mở phiếu — tab Lương trước, drill-down HH.

### 2026-07-26 - Wage prorate + HH/KPI detail tabs
- Goal: Lương cứng theo ngày HĐ trong kỳ; tab chi tiết HH (SP/đơn/SL/giá/CK/HH) + KPI; thưởng ca 1 dòng/session.
- Changes made: `_spa_prorate_contract_wage` + audit fields; models `commission.line` / `kpi.line`; rebuild trong recompute; smart buttons; shift bonus per-session `source_*`; tests + docs.
- Files touched: `models/spa_staff_payroll.py`, `spa_staff_payroll_detail_line.py`, generate wizard, views, security, tests, AGENT_REFERENCE, DECISIONS, WORKLOG
- Validation done: `--test-tags=/spa_staff_payroll` trên `drlai` — **0 failed, 0 error(s) of 32 tests**.
- Dependency impact check:
  - Dependents reviewed: generate wizard wage; ranking year wage=0; cash-basis HH/KPI tests; long_shift assertions (`source_id`); spa/booking_calendar không đổi code.
  - Contract compatibility result: additive detail models; ledger HH/KPI vẫn 1 dòng tổng; shift bonus số dòng tăng (tổng tiền giữ).
  - Regression tests/manual checks run: module test suite.
- Open risks: phiếu cũ đã tạo trước upgrade giữ wage full-month đến khi bấm «Lấy từ hợp đồng» / tạo lại.
- Next suggested steps: UAT phiếu Jul HĐ từ 15; đối chiếu tab HH với SO.

### 2026-07-26 - Full commission/KPI test suite
- Goal: Bổ sung T1–T9 + helpers; chạy full `/spa_staff_payroll`.
- Changes made: helpers `_make_comm_product` / `_make_so_with_invoice` / `_payroll_for_month`; tests partial, multi-%, KPI, HĐ lẻ paid-date, wrong user, not invoiced, no double-count, ranking, pct0.
- Files touched: `tests/test_spa_staff_payroll.py`, `docs/AGENT_REFERENCE.md`, `docs/WORKLOG.md`
- Validation done: 28 tests, 0 failed (`--test-tags=/spa_staff_payroll` trên `drlai`).
- Dependency impact check:
  - Dependents reviewed: ranking `_scores_sales`; payroll KPI/HH helpers.
  - Contract compatibility result: chỉ test/docs.
  - Regression tests/manual checks run: `--test-tags=/spa_staff_payroll`.
- Open risks: downpayment/credit-note chưa cover (tránh flaky).
- Next suggested steps: UAT SO cọc thật trên UI.

### 2026-07-26 - Sales commission on SO settled (cash-basis)
- Goal: HH khi SO thu đủ (residual=0); kỳ = ngày đủ tiền; base sau CK dòng.
- Changes made: depend `sale`; helpers settled/paid-date; KPI+HH+ranking sales cùng DEC; test SO May→July; docs.
- Files touched: `__manifest__.py`, `models/spa_staff_payroll.py`, `wizards/spa_payroll_ranking_wizard.py`, tests, README, AGENT_REFERENCE, DECISIONS, WORKLOG
- Validation done: targeted commission tests.
- Dependency impact check:
  - Dependents reviewed: ranking `_scores_sales`; payroll recompute KPI/HH.
  - Contract compatibility result: thêm depend `sale` (đã có qua `spa`); đổi điều kiện kỳ từ invoice_date → paid date.
  - Regression tests/manual checks run: `test_sales_commission_*`.
- Open risks: payment register VietQR required trên UI; test dùng `account.payment` trực tiếp.
- Next suggested steps: UAT SO cọc/trả đủ trên DB thật.

### 2026-07-26 - Seed default payroll tiers / KPI
- Goal: Seed XML global (company trống) KPI/long/requested/prizes; align ensure + post_init.
- Changes made: `data/spa_payroll_default_tiers_data.xml` noupdate; manifest; `_spa_ensure_default_tiers` tạo/search `company_id=False`; `post_init_hook`; test + docs.
- Files touched: `data/spa_payroll_default_tiers_data.xml`, `__manifest__.py`, `__init__.py`, `models/payroll_config.py`, `tests/test_spa_staff_payroll.py`, `README.md`, `docs/AGENT_REFERENCE.md`, `docs/WORKLOG.md`
- Validation done: `-u spa_staff_payroll` + test load tiers.
- Dependency impact check:
  - Dependents reviewed: payroll tier pick (`| False | company`); ranking prize search same pattern; wizard load tiers.
  - Contract compatibility result: ensure vẫn public; seed đổi sang global thay vì gắn company hiện tại.
  - Regression tests/manual checks run: `test_load_default_tiers_idempotent`; UI KPI menu sau upgrade.
- Open risks: DB cũ đã nạp wizard theo company có thể còn bản ghi company-specific cạnh global (ưu tiên company).
- Next suggested steps: UAT menu Bậc KPI / ca dài.

### 2026-07-26 - Sales commission % on product.category
- Goal: % thưởng bán hàng theo danh mục; ẩn field trên SP; calc walk parent.
- Changes made: field trên category; `_spa_get_sales_commission_percent`; UI ẩn SP; payroll dùng helper; tests + docs.
- Files touched: `models/product_payroll.py`, `models/spa_staff_payroll.py`, `views/product_payroll_views.xml`, tests, README, AGENT_REFERENCE, WORKLOG
- Validation done: targeted payroll tests.
- Dependency impact check:
  - Dependents reviewed: payroll commission calc; product category form.
  - Contract compatibility result: giữ field SP trong DB; đổi nguồn tính sang category.
  - Regression tests/manual checks run: suite tags.
- Open risks: none.
- Next suggested steps: migrate data cũ từ SP → category nếu cần.

### 2026-07-26 - Profile payroll company_id optional
- Goal: Để trống Công ty trên profile = dùng chung mọi công ty.
- Changes made: `required=False`, bỏ default company; currency compute khi không có company; domain SP `| False | company`; test + README/AGENT_REFERENCE.
- Files touched: `models/product_payroll.py`, `views/product_payroll_views.xml`, `tests/test_spa_staff_payroll.py`, `README.md`, `docs/AGENT_REFERENCE.md`, `docs/WORKLOG.md`
- Validation done: test `test_profile_without_company_usable_on_product` (suite payroll).
- Dependency impact check:
  - Dependents reviewed: product.template domain; payout line Monetary currency.
  - Contract compatibility result: field vẫn tên `company_id`; chỉ nới required.
  - Regression tests/manual checks run: targeted suite.
- Open risks: none.
- Next suggested steps: none.

### 2026-07-26 - Implement payroll full roadmap (phases 0–4)
- Goal: SoT ledger + sync flags; seed/tiers; ranking tháng/năm; thâm niên display; PDF; mitigations.
- Changes made: multi-therapist split; booking↔session sync; company rules; to_approve; lunch_min_minutes; load-tiers wizard; ranking prize/result; seniority; QWeb PDF; tests.
- Files touched: `models/*`, `wizards/*`, `views/*`, `security/*`, `report/*`, `tests/*`, `docs/*`, `__manifest__.py`, `README.md`
- Validation done: `-u spa_staff_payroll --test-tags=/spa_staff_payroll` trên `drlai` — 15 tests, 0 failed.
- Dependency impact check:
  - Dependents reviewed: spa session/booking; hr employee; account moves KPI/ranking.
  - Contract compatibility result: thêm `to_approve`, `ranking_bonus`, fields mới — không rename cũ.
  - Regression tests/manual checks run: suite green.
- Open risks: flag SOP; KPI invoice_user; ranking năm/OT amount=0 cần QL nhập.
- Next suggested steps: UAT nạp bậc; cấu hình profile 4 cấp × SP; chốt xếp hạng tháng mẫu.

### 2026-07-26 - Booking Operator (no payroll code change)
- Goal: Session note — `spa_staff_payroll` không sửa code khi thêm Spa Booking Operator / Lịch phục vụ.
- Changes made: docs-only handoff.
- Files touched: `docs/WORKLOG.md`
- Validation done: n/a (không đổi payroll).
- Dependency impact check:
  - Dependents reviewed: calendar color/constraints trên booking state — operator chỉ chuyển confirmed→doing→done; màu doing/done giữ logic cũ.
  - Contract compatibility result: không đổi contract payroll.
  - Regression tests/manual checks run: n/a.
- Open risks: không.
- Next suggested steps: không.

### 2026-07-26 - Baseline analysis → memory docs
- Goal: Phân tích hiện trạng `spa_staff_payroll` và đưa vào bộ memory docs chuẩn (AGENT_REFERENCE / BUG_LOG / DECISIONS / WORKLOG); gắn vào session defaults Agent.
- Changes made: docs-only — tạo `docs/` quartet; cập nhật `docs/AGENT_SESSION_DEFAULTS.md`, `AGENTS.md`, `.cursor/skills/project-memory-maintenance/SKILL.md`; pointer ngắn trong README.
- Files touched:
  - `custom_addons/spa_staff_payroll/docs/AGENT_REFERENCE.md` (new)
  - `custom_addons/spa_staff_payroll/docs/BUG_LOG.md` (new)
  - `custom_addons/spa_staff_payroll/docs/DECISIONS.md` (new)
  - `custom_addons/spa_staff_payroll/docs/WORKLOG.md` (new)
  - `custom_addons/spa_staff_payroll/README.md` (pointer)
  - `docs/AGENT_SESSION_DEFAULTS.md`
  - `AGENTS.md`
  - `.cursor/skills/project-memory-maintenance/SKILL.md`
- Validation done: đọc đối chiếu models/wizard/README; không chạy test payroll (không đổi code logic).
- Dependency impact check:
  - Dependents reviewed: spa (session, staff level, product salary fields), booking_calendar (calendar colors/constraints via payroll inherit), account (KPI/commission), hr/hr_contract (wage/OT) — chỉ tài liệu hóa coupling.
  - Contract compatibility result: không đổi model/field/XML id/hành vi runtime.
  - Regression tests/manual checks run: n/a (docs-only).
- Open risks: PAY-BUG-2026-07-26-01 double-count; PAY-BUG-2026-07-26-02 booking→session flags; PAY-BUG-2026-07-26-03 dayoff display-only.
- Next suggested steps: chốt DEC cho path tiền công buổi duy nhất; sync hoặc đọc flag từ booking; bổ sung test KPI/lunch/wizard/double-count.
