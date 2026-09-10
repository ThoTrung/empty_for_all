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

### 2026-09-09 - Đơn có trả hàng lọt KPI/HH (fix ở `spa`, engine payroll không đổi)
- Goal: Đơn bán có credit note trả hàng một phần bị loại hoàn toàn khỏi KPI + hoa hồng (bug S53056) vì SO không bao giờ có `spa_settled_date`. Sửa nguồn sự thật settlement trong module `spa`; **`spa_staff_payroll` không sửa logic** — chỉ thêm test.
- Changes made:
  - `spa/models/sale_order.py`: `_spa_order_is_closed_by_returns()` (so **theo số tiền** `amount_to_invoice ≈ Σ posted_refunds.amount_total`, không khớp dòng); `spa_settled_date` **ghi 1 lần rồi đóng băng**; ngày gốc từ move không-refund. `spa_is_settled` không đổi.
  - `spa/models/spa_revenue_report_mixin.py`: bỏ guard `>=` trong `_spa_where_refund_adjustment`.
  - `spa_staff_payroll/tests/test_spa_staff_payroll.py`: 5 test mới (partial/full return cùng tháng, multi-return 2 tháng, delivery-policy giới hạn, mixed-policy) — assert số **hardcode**, `spa_settled_date` ngày chính xác, `spa_is_settled` False. Helper `_make_policy_comm_product` set `taxes_id=[]` để số sạch.
  - `spa_staff_payroll/models/account_move_payroll.py`: 1 dòng comment (bỏ chữ `flush_all` khỏi comment giải thích — sửa `test_late_refund_notify_flush_uses_narrow_model_flush` vốn fail sẵn do so khớp chuỗi ngây thơ; không đổi hành vi).
  - `docs/DECISIONS.md`: [PAY-DEC-2026-09-09-01] (cập nhật bản round 2).
- Files touched: `spa/models/sale_order.py`, `spa/models/spa_revenue_report_mixin.py`, `spa/tests/*`, `spa/docs/*`, `spa_staff_payroll/tests/test_spa_staff_payroll.py`, `spa_staff_payroll/models/account_move_payroll.py`, `spa_staff_payroll/docs/DECISIONS.md`, `spa_staff_payroll/docs/WORKLOG.md`.
- Validation done: full `spa` + `spa_staff_payroll` suites trên DB throwaway; baseline diff (stash 2 file spa) → 0 regression mới. Regression flagged (`test_late_refund_keeps_origin_month...`, `test_card_return_commission_no_double_clawback`, `test_kpi_so_settled_month_july_not_may`, `test_sales_commission_so_partial_payment_no_hh`, toàn bộ revenue-report/stats/dashboard) đều xanh.
- Dependency impact check:
  - Dependents reviewed: `_spa_sale_orders_settled_in_period` / `_spa_so_linked_refunds_paid_in_period` / `_spa_net_invoice_revenue_for_sales_user` — key theo `spa_settled_date` (stored), guard "linked order có spa_settled_date" nay pass cho đơn kiểu S53056. Không đổi công thức HH/KPI.
  - Contract compatibility result: `kpi_revenue_base` / `sales_commission` cho đơn có trả hàng nay = net (bucket 1 gộp + bucket 3 CN âm); phiếu `done` không tự sửa.
  - Regression tests/manual checks run: 53 test `spa_staff_payroll` (gồm 5 mới) + suite `spa`.
- Open risks: giới hạn `invoice_policy='delivery'` + restock (xem [PAY-DEC-2026-09-09-01] / [SPA-DEC-2026-09-09-08]); deploy cần recompute thủ công `drlai` (§Deploy trong plan).
- Next suggested steps: §Deploy trên `drlai`; recompute phiếu lương draft có kỳ xuất hiện `spa_settled_date` mới.

### 2026-09-03 - Global discount prorated into commission; card-return double-clawback fixed
- Goal: Đóng "open risk" HH ≠ KPI khi có CK toàn đơn (PAY-DEC-2026-08-29-01); điều tra và sửa double-clawback hoa hồng khi khách trả thẻ dịch vụ (2 agent điều tra độc lập + 1 agent review, tự đọc code xác nhận trước khi sửa).
- Changes made: `_spa_global_discount_share_untaxed()` mới, trừ vào subtotal trước khi tính `commission_amount` (SO + invoice); field `sale.order.is_card_return_order` loại đơn trả thẻ khỏi `_spa_sale_orders_settled_in_period`; `spa_card_upgrade_wizard.py` sửa default `credit_old_card` (giá đã bán gốc) + `user_id` (salesperson gốc) cho nhánh `return`. Xem [PAY-DEC-2026-09-03-01].
- Files touched:
  - `custom_addons/spa_staff_payroll/models/spa_staff_payroll.py`
  - `custom_addons/spa/models/sale_order.py`
  - `custom_addons/spa/wizards/spa_card_upgrade_wizard.py`
  - `custom_addons/spa_staff_payroll/tests/test_spa_staff_payroll.py`
  - `docs/DECISIONS.md`
- Validation done: `-u spa,spa_staff_payroll --test-enable --test-tags /spa_staff_payroll` trên bản sao DB dev (`drlai`) → 0 failed, 0 error (40 tests, gồm 3 test mới + 1 test cập nhật kỳ vọng).
- Dependency impact check:
  - Dependents reviewed: `_spa_net_invoice_revenue_for_sales_user` (dùng chung `_spa_sale_orders_settled_in_period`, tự động fix theo); KPI `net_rev` (cùng nguồn `orders`, tự động fix double-count).
  - Contract compatibility result: `spa.staff.payroll.commission.line.price_subtotal`/`commission_amount` cho dòng có CK toàn đơn nay là giá trị NET (khác giá trị cũ) — không hồi tố phiếu `done`.
  - Regression tests/manual checks run: toàn bộ `TestSpaStaffPayroll` (40 tests).
- Open risks: double-clawback trả thẻ trong quá khứ (nếu có giao dịch trước fix) không được rà soát lại — theo quyết định người dùng, chỉ chặn từ nay về sau.
- Next suggested steps: nếu phát sinh nhu cầu, cân nhắc rà soát thủ công các phiếu lương `done` cũ có liên quan trả thẻ.

### 2026-08-29 - Note: spa Dashboard month snapshot (no payroll code)
- Goal: Confirm payroll không đọc `spa.dashboard.month.line`; KPI vẫn helper SO live.
- Changes made: none in this module.
- Files touched: `docs/AGENT_REFERENCE.md` (note only)
- Validation done: n/a
- Dependency impact check:
  - Dependents reviewed: KPI/ranking `_spa_recognized_amount_total`; không inherit dashboard RPC.
  - Contract compatibility result: no impact.
  - Regression tests/manual checks run: none
- Open risks: none
- Next suggested steps: none

### 2026-08-29 - KPI = spa recognized net CK
- Goal: Phiếu lương KPI/ranking khớp Dashboard DT (trừ cọc, đã trừ CK).
- Changes made: `_spa_recognized_amount_total` cho KPI + ranking; HH skip `is_global_discount`.
- Files touched: `spa_staff_payroll.py`, detail_line help, tests, docs
- Validation done: cùng lần 62 tests trên `drlai` → **0 failed**.
- Dependency impact check:
  - Dependents reviewed: ranking `_spa_net_invoice_revenue_for_sales_user`; spa helper SoT; booking không đụng.
  - Contract compatibility result: helper công khai mới trên SO; phiếu done không tự sửa.
  - Regression tests/manual checks run: TestSpaStaffPayroll.
- Open risks: recompute draft sau upgrade; HH ≠ KPI khi có CK toàn đơn.
- Next suggested steps: Tính lại phiếu draft tháng có CK.

### 2026-08-29 - Note: spa revenue-report HTML lần thu (no payroll code)
- Goal: Confirm payroll không đọc HTML lần thu trên order report.
- Changes made: none in this module.
- Files touched: none
- Validation done: n/a
- Dependency impact check:
  - Dependents reviewed: KPI/HH vẫn `spa_settled_*`; không đọc `spa_invoice_html`.
  - Contract compatibility result: no impact.
  - Regression tests/manual checks run: none in this module.
- Open risks: none
- Next suggested steps: none

### 2026-08-29 - Note: spa HĐ-from-SO + dashboard drill (no payroll code)
- Goal: Confirm payroll vẫn ủy quyền settled trên `sale.order`; không tạo HĐ lẻ.
- Changes made: none in this module.
- Files touched: none
- Validation done: n/a
- Dependency impact check:
  - Dependents reviewed: helpers `spa_settled_*` / `spa_fully_paid_date` không đổi tên; KPI/HH từ SO settled.
  - Contract compatibility result: no impact. HĐ lẻ leftover vẫn có thể vào SQL DT spa nếu đã post trước guard.
  - Regression tests/manual checks run: none in this module.
- Open risks: none
- Next suggested steps: none

### 2026-08-28 - Clawback CN tháng refund + nới spa_is_settled
- Goal: Đồng bộ lương với thống kê settled: tháng gốc giữ khi refund muộn; tháng refund trừ KPI/HH nếu phiếu draft; phiếu done → activity.
- Changes made: domain settled chỉ `spa_settled_date`; helper CN gắn SO; HH invoice sign âm cho refund; inherit `_spa_mark_settlement_recompute` tạo activity.
- Files touched: `spa_staff_payroll.py`, `account_move_payroll.py`, `models/__init__.py`, tests, docs.
- Validation done: `--test-tags=/spa_staff_payroll:TestSpaStaffPayroll` trên `drlai` (cùng lần spa stats) → 0 failed.
- Dependency impact check:
  - Dependents reviewed: ranking `_spa_net_invoice_revenue_for_sales_user` gồm clawback CN; `spa` settlement fields không đổi tên; `booking_calendar` không đụng.
  - Contract compatibility result: helper công khai giữ tên; nới domain (cố ý).
  - Regression tests/manual checks run: commission/KPI cũ + `test_late_refund_*`.
- Open risks: activity phụ thuộc hook reconcile; CN không qua payment thì không notify.
- Next suggested steps: none.

### 2026-08-26 - Delegate settled helpers to spa settlement fields
- Goal: Một nguồn sự thật settled với màn doanh thu spa (SPA-DEC-2026-08-26-01).
- Changes made: `_spa_is_sale_order_settled` / `_spa_sale_order_settled_date` / `_spa_invoice_fully_paid_date` / `_spa_sale_orders_settled_in_period` ủy quyền field/helper spa; domain search theo `spa_settled_date` khi có.
- Files touched: `models/spa_staff_payroll.py`, docs.
- Validation done: settled May→July commission + KPI July → **0 failed / 2 tests** trên `drlai`.
- Dependency impact check:
  - Dependents reviewed: commission/KPI/ranking sales paths dùng helpers trên; không đổi signature công khai.
  - Contract compatibility result: tương thích; spa phải upgraded trước/cùng lúc.
  - Regression tests/manual checks run: TestSpaStaffPayroll settled/KPI tags.
- Open risks: nếu spa chưa upgrade, fallback legacy vẫn chạy.
- Next suggested steps: none for payroll; theo phase 2 thống kê spa.

### 2026-08-25 - Product form: Payroll Spa above composite, table 50%
- Goal: Khối Payroll Spa (theo profile) nằm trên Dịch vụ tổng; bảng payout rộng 50%.
- Changes made: xpath `position="before"` `group_spa_composite_service`; outer+inner group 50%; help dưới bảng `colspan="2"`.
- Files touched: `views/product_payroll_views.xml`, `tests/test_spa_staff_payroll.py` (`TestSpaPayrollProductFormLayout`), docs.
- Validation done: `--test-tags=/spa:TestSpaProductTemplateFormLayout,/spa_staff_payroll:TestSpaPayrollProductFormLayout` trên `drlai` → **0 failed, 0 error(s) of 2 tests**.
- Dependency impact check:
  - Dependents reviewed: `spa.view_spa_inherit_product_template_form` (`group_spa_composite_service`); không đụng phiếu lương / booking form.
  - Contract compatibility result: XML id view không đổi; field `spa_payroll_profile_payout_line_ids` không đổi.
  - Regression tests/manual checks run: TestSpaPayrollProductFormLayout.
- Open risks: none for layout; cần `-u spa_staff_payroll` vì XML view.
- Next suggested steps: smoke UI form dịch vụ — Payroll trên Dịch vụ tổng, cột cấp NV không bị cắt.

### 2026-08-19 - Note: booking tree columns (no payroll code change)
- Goal: Confirm payroll không inherit tree booking khi đổi cột / default_order.
- Changes made: none in this module.
- Files touched: none
- Validation done: n/a
- Dependency impact check:
  - Dependents reviewed: `spa_booking_payroll_views.xml` chỉ inherit form staff + form operator.
  - Contract compatibility result: no impact.
  - Regression tests/manual checks run: none
- Open risks: none
- Next suggested steps: none

### 2026-08-19 - Operator form: readonly payroll flags
- Goal: Operator `edit=1` không sửa được flag ca dài / khách đặt NV.
- Changes made: inherit `view_spa_service_booking_form_operator`, readonly `spa_payroll_shift_kind` + `spa_payroll_customer_requested`.
- Files touched: `views/spa_booking_payroll_views.xml`, `tests/test_spa_staff_payroll.py`, docs.
- Validation done: `TestSpaPayrollOperatorBookingForm` trên DB `drlai`.
- Dependency impact check:
  - Dependents reviewed: form staff (không đổi); booking_calendar operator write vẫn reject payroll keys.
  - Contract compatibility result: additive inherit.
  - Regression tests/manual checks run: TestSpaPayrollOperatorBookingForm.
- Open risks: xpath fail nếu payroll field bị nhân đôi trên form operator — hiện 1 cặp field.
- Next suggested steps: `-u spa_staff_payroll`.

### 2026-08-03 - Note: spa loyalty pre-deploy check (no code change)
- Goal: Confirm no payroll impact before spa loyalty cancel prod deploy.
- Changes made: none
- Files touched: none
- Validation done: n/a
- Dependency impact check:
  - Dependents reviewed: payroll không đọc spa.loyalty.ledger cancel.
  - Contract compatibility result: no impact.
  - Regression tests/manual checks run: none
- Open risks: none
- Next suggested steps: none

### 2026-08-02 - Note: spa loyalty residual risk register (no code change)
- Goal: Mirror spa docs — residual risk register for loyalty cancel.
- Changes made: none in this module.
- Files touched: none (spa docs only).
- Validation done: n/a
- Dependency impact check:
  - Dependents reviewed: payroll không đọc loyalty ledger.
  - Contract compatibility result: no impact.
  - Regression tests/manual checks run: none
- Open risks: none for this module
- Next suggested steps: none

### 2026-08-02 - Note: spa loyalty cancel cleanup (no code change)
- Goal: Ghi nhận task spa dọn `spa.loyalty.ledger` khi hủy SO/HĐ.
- Changes made: none in this module.
- Files touched: none
- Validation done: n/a
- Dependency impact check:
  - Dependents reviewed: payroll không đọc loyalty ledger.
  - Contract compatibility result: no impact.
  - Regression tests/manual checks run: none
- Open risks: none
- Next suggested steps: none

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
