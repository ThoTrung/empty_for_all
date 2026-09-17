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

### [PAY-DEC-2026-09-09-01] Đơn có trả hàng ("closed by returns") vẫn vào KPI/HH
- Date: 2026-09-09
- Status: accepted
- Context: Đơn bán SP `invoice_policy='order'` có **trả hàng một phần** (credit note `out_refund` posted+paid) bị loại HOÀN TOÀN khỏi KPI + hoa hồng — cả phần bán lẫn phần trả (ví dụ S53056, DB `drlai`, phiếu id=13). Nguyên nhân: `sale.order._spa_order_is_settled()` fail ở `currency.is_zero(amount_to_invoice)` — trả 5/10 cái làm `qty_invoiced` 10→5 nên `amount_to_invoice` quay lại > 0 và **không bao giờ về 0** (khách đã trả, không xuất HĐ tiếp) ⇒ SO không bao giờ có `spa_settled_date` ⇒ cả 3 bucket doanh thu payroll bỏ qua. Khác case late-refund (`PAY-DEC-2026-08-28-01`): ở đó đơn settled trước rồi mới hoàn.
- Decision (bản sau review + user chốt 2026-09-09):
  - `sale.order` (module `spa`): thêm **duy nhất** `_spa_order_is_closed_by_returns()` — kiểm tra **theo số tiền, KHÔNG khớp dòng**: `state in (sale,done)` + ≥1 `out_refund` posted liên kết + mọi HĐ/CN posted đã paid + ≥1 refund đã paid + `currency.is_zero(order.amount_to_invoice − Σ posted_refunds.amount_total)` (cả 2 vế tax-incl). Đại số Odoo core: `amount_to_invoice = (amount_total − invoiced) + refunded` ⇒ phép so = `amount_total − invoiced` = 0 chỉ khi đơn đã xuất đủ HĐ trước khi trả; còn hàng chờ HĐ ⇒ > 0; over-return ⇒ < 0. **Không cần `sale_line_ids`** nên CN thiếu link (1/460 toàn DB) cũng chạy. (Vòng 1 dùng `_spa_returned_qty_by_line()` khớp dòng — **đã xóa** vì khớp nhầm khi 1 SP nằm trên nhiều dòng SO.)
  - `_spa_order_settled_date()`: guard mở đón cả `_spa_order_is_closed_by_returns()`; ngày gốc tính từ `out_invoice`/`out_receipt` khi có (chỉ loại `out_refund` khi còn ≥1 move không phải refund) — đơn "đóng bằng trả hàng" quy về **tháng HĐ bán**; đơn trả thẻ (chỉ out_refund) vẫn ra ngày.
  - `_compute_spa_settlement()`: **`spa_settled_date` ghi 1 lần, đóng băng vĩnh viễn** — `if not prev_date and (is_settled or _spa_order_is_closed_by_returns()): ...`. Đã có ngày ⇒ **không bao giờ đổi** (thêm HĐ bán thứ 2, hoàn muộn, đảo thanh toán — đều không dời). **`spa_is_settled` KHÔNG đổi** — vẫn `_spa_order_is_settled()` strict (dashboard `spa_owner_dashboard.py:142`, `spa_stats_filter_wizard.py:360`, test `spa`).
  - `@api.depends` của `_compute_spa_settlement`: bỏ các depends theo dòng đơn (vòng 1) — `amount_to_invoice` + `invoice_ids.state/move_type/payment_state/amount_residual/amount_total` là đủ.
  - SQL view (`spa_revenue_report_mixin._spa_where_refund_adjustment`): bỏ predicate `am.spa_fully_paid_date >= so.spa_settled_date` (ngày gốc nay = ngày HĐ bán paid; CN hoàn **trước** ngày đó vẫn là điều chỉnh âm hợp lệ — giữ guard làm rớt dòng âm ⇒ **khai khống** doanh thu so với payroll).
  - Payroll: **không sửa logic** — khi SO có `spa_settled_date`, bucket 1 đếm SO gộp (`_spa_recognized_amount_total`) + bucket 3 claw-back credit note (sign âm) tự cho net đúng.
- Consequences:
  - `-u spa` KHÔNG tự recompute stored field — cần recompute thủ công 415 đơn `drlai` (runbook trong plan / §Deploy). Phiếu `done` không tự sửa (`mail.activity` + dòng tay như `PAY-DEC-2026-08-28-01`).
  - Báo cáo doanh thu SQL kỳ CŨ có thể **đổi số** (thêm dòng điều chỉnh âm cho CN hoàn sớm trước đây bị guard chặn) — cảnh báo runbook.
  - **Giới hạn đã biết** (tách ticket):
    - Phép so = `amount_total − invoiced_gross`, chỉ = 0 khi đơn từng xuất **đủ** HĐ (gross). SP `invoice_policy='delivery'` **chưa giao đủ** rồi bị **bỏ dở** sau khi trả phần đã giao ⇒ `amount_total − invoiced_gross > 0` (còn hàng chưa giao) ⇒ đơn **không** "đóng bằng trả hàng" ⇒ nếu đơn đó chưa từng settled sẽ vẫn rớt KPI/HH. Đúng về kế toán, chỉ thành vấn đề khi đơn bị bỏ dở thật. Restock hàng **đã giao đủ** không làm mất KPI (phép so key theo gross đã xuất HĐ, không theo `qty_delivered`).
    - `Σ posted_refunds.amount_total` đo **toàn bộ** credit note liên kết. Nếu 1 credit note còn mang dòng credit **không liên quan** đơn này, hoặc 1 credit note đảo **2 đơn**, thì `Σ` đo sai phần đã trả của đơn ⇒ thường thành **false negative** (đơn rớt khỏi KPI, cùng loại với bug gốc — an toàn, không tính khống). Không xảy ra qua flow "trả hàng từ hóa đơn" chuẩn của spa (credit note reversal 1-1).
    - Chưa có test cho **cọc (down-payment) + trả hàng một phần**. Đại số `amount_total − invoiced_gross` vẫn đúng khi có dòng cọc (cọc chỉ là advance, `amount_to_invoice` core đã trừ), nhưng đặt cọc phổ biến ở spa ⇒ nên bổ sung test khi có dịp.
    - **Write-once**: recompute thường **không** tự sửa `spa_settled_date` đã lưu SAI (ví dụ đơn từng lưu ngày sai trước fix). Phải `order.write({'spa_settled_date': False})` **rồi** mới `_compute_spa_settlement()`. Runbook §Deploy phải nêu. Hệ quả phụ: đơn **nhiều HĐ bán** (cọc + HĐ cuối) — hook reconcile có thể freeze theo ngày HĐ **sớm hơn** nếu `spa_fully_paid_date` HĐ cuối chưa kịp tính; thường cùng tháng (không lệch kỳ), chỉ lệch nếu 2 HĐ cách tháng.
- Alternatives considered: vá riêng engine payroll (loại — sửa nguồn sự thật); nới `spa_is_settled` (loại — regression dashboard/test); khớp CN↔dòng SO theo qty (loại — M1: khớp nhầm SP đa dòng); `spa_settled_date` tính lại mỗi recompute (loại — M2: đơn nhiều HĐ nhảy tháng); thêm SQL fallback `reversed_entry_id` (loại — 1/460, không cần vì so số tiền).
- Related files/modules: `spa/models/sale_order.py`, `spa/models/spa_revenue_report_mixin.py`, `spa_staff_payroll/models/spa_staff_payroll.py` (rà, không sửa), `spa_staff_payroll/tests/test_spa_staff_payroll.py`, `spa/tests/test_spa_order_closed_by_returns.py`, `spa/tests/test_spa_revenue_report.py`, `spa/docs/DECISIONS.md` (SPA-DEC-2026-09-09-08).

### [PAY-DEC-2026-08-29-01] KPI/ranking = spa recognized (net CK, trừ cọc)
- Date: 2026-08-29
- Status: accepted
- Context: `kpi_revenue_base` / ranking dùng `sale.order.amount_total` (có cọc, đã trừ CK); Dashboard order-grain trước đó loại CK → lệch.
- Decision: SO dùng `sale.order._spa_recognized_amount_total()`. CN + HĐ lẻ giữ `amount_total_signed`. HH skip `is_global_discount`. Phiếu `done` không tự sửa.
- Consequences: draft recompute sau upgrade spa+payroll. HH có thể ≠ KPI.
- Alternatives considered: giữ amount_total (rejected — lệch Dashboard / dòng cọc).
- Related files/modules: `spa_staff_payroll.py`, spa helper, tests.

### [PAY-DEC-2026-08-28-01] Eligibility theo spa_settled_date + clawback CN tháng refund
- Date: 2026-08-28
- Status: accepted
- Context: Late refund unset `spa_is_settled` nhưng giữ `spa_settled_date`; domain cũ `spa_is_settled=True` làm mất đơn khỏi tháng gốc khi recompute phiếu draft. Product: clawback KPI/HH tháng refund; phiếu `done` không sửa.
- Decision:
  - `_spa_sale_orders_settled_in_period`: chỉ `spa_settled_date ∈ kỳ` (không đòi `spa_is_settled`).
  - `_spa_sale_order_settled_date` ưu tiên stored `spa_settled_date`.
  - SO-linked `out_refund` paid trong kỳ → KPI `amount_total_signed` + HH dòng CN (sign âm). Không đi nhánh standalone.
  - Phiếu `done` cùng kỳ refund: `mail.activity` todo; QL thêm `payroll.line` `is_manual`.
- Consequences: ranking doanh số net thêm clawback CN gắn SO. Công thức HH category không đổi.
- Alternatives considered: payroll đọc bảng stat copy (rejected); model `spa.stat.payroll.adjustment` (rejected — dùng activity + dòng tay).
- Related files/modules: `spa_staff_payroll.py`, `account_move_payroll.py`, tests.

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

### [PAY-DEC-2026-09-16-01] Điểm/voucher trừ tiền phân bổ vào HH/KPI như CK toàn đơn; KPI chuyển sang untaxed
- Date: 2026-09-16
- Status: accepted
- Context: điều tra (1 agent nghiên cứu + 1 agent review độc lập, tự đọc code xác nhận, cộng với review thủ công của chủ dự án) phát hiện dòng âm sinh từ đổi điểm (`spa.redeem.points.wizard`) và voucher giảm tiền/% (`spa.apply.voucher.wizard`, cùng dùng sản phẩm "Reward" cấu hình ở `spa_loyalty.reward_product_id`) KHÔNG được xử lý giống CK toàn đơn (`is_global_discount`): dòng thưởng bị coi như một "sản phẩm" bình thường, có thể sinh HH âm sai tỷ lệ nếu danh mục cha có % > 0, hoặc bị bỏ qua hoàn toàn nếu % = 0 (HH tính trên giá gộp). Đối chiếu số liệu thủ công trong `input_claude_data/T8.26-Phương spa_new.xlsx` (dù case cụ thể trong Excel hoá ra là CK toàn đơn thường, không phải điểm) xác nhận công thức phân bổ đúng phải giống hệt CK. Review độc lập còn phát hiện thêm 2 lỗi có sẵn không liên quan trực tiếp tới điểm/voucher nhưng cùng gốc: (a) helper phân bổ CK cũ luôn trả 0 trên hoá đơn/credit note (vì lọc `not l.display_type`, trong khi AML dùng `display_type='product'`); (b) `return` đặt sai trong vòng lặp `_reverse_moves` nên chỉ credit note đầu tiên được xử lý khi đảo nhiều hoá đơn cùng lúc.
- Decision:
  1. Thêm field `spa_is_order_discount_line` (Boolean, copy mặc định — KHÔNG `copy=False`, để credit note tạo bằng `copy()` tự giữ cờ) trên `sale.order.line` và `account.move.line` (module `spa`). Gán bởi cả 2 wizard (trừ nhánh voucher tặng SP thật, giá 0 — không cần cờ vì HH đã tự = 0). Predicate dùng chung `line._spa_is_order_level_discount()` = `is_global_discount OR spa_is_order_discount_line`.
  2. Payroll dùng helper KHÔNG LƯU `sale.order._spa_order_discount_share_map()` / `account.move._spa_order_discount_share_map()` (module `spa`, hàm chung `spa_order_discount_share_map` ở `spa/helper/order_discount.py`) — tính trong một lượt cho mọi dòng giảm giá cấp đơn (CK + điểm + voucher), mẫu số loại bỏ section/cọc/chính các dòng giảm giá, làm tròn kiểu largest-remainder để tổng khớp. `_spa_commission_detail_vals_for_sale_order`/`_for_invoice` (`spa_staff_payroll.py`) bỏ hẳn `_spa_global_discount_share_untaxed` cũ, skip tường minh mọi dòng `_spa_is_order_level_discount()`, cộng share vào `price_subtotal` trước khi nhân %. Điều này đồng thời fix (a) ở Context, vì helper mới lọc đúng `display_type` theo từng loại model.
  3. `spa/models/account_move.py._reverse_moves`: sửa (b) — đưa `return` ra ngoài vòng for. Thêm `_spa_rebalance_order_discount_lines()` (gọi cuối `_reverse_moves` khi `not cancel`, trong `update_onchange_move_line_quantity` khi là credit note nháp, và đầu `action_post`): tính lại dòng CK/điểm/voucher trên credit note theo tỷ lệ `Σ dòng giảm giá / Σ dòng hàng` của **hoá đơn gốc**, áp cho phần hàng thực sự bị hoàn trên credit note; dòng sinh lại copy `account_id`/`tax_ids`/`sale_line_ids` từ dòng gốc (không dùng `property_account_income_id` fallback) để không lọt vào nhánh "bán lẻ" của báo cáo doanh thu.
  4. Báo cáo doanh thu theo SP (`spa.revenue.report`) đổi từ "ẩn dòng CK" sang "ẩn + phân bổ CK/điểm/voucher vào từng dòng SP còn lại (net)" bằng SQL window function, để tổng báo cáo theo SP khớp báo cáo theo đơn (`spa.revenue.order.report`, vốn đã net sẵn). Sửa kèm lỗi `-ABS(...)` sai dấu với dòng đã có dấu âm.
  5. **KPI và bảng xếp hạng doanh số chuyển từ có-thuế sang chưa-thuế** (theo yêu cầu tường minh của chủ dự án): `_spa_net_invoice_revenue_for_sales_user` và `action_recompute_payroll_extras` dùng `order._spa_recognized_amount_untaxed()` (đã có sẵn ở `spa/models/sale_order.py`) và `move.amount_untaxed_signed` thay cho `_spa_recognized_amount_total()`/`amount_total_signed`. HH vẫn luôn untaxed như cũ, nay KPI cùng cơ sở.
  6. Migration `spa` 1.0.4: pre-migration tạo cột bằng SQL (tránh ORM tính lại toàn bảng `account_move_line`); post-migration gán cờ cho dữ liệu cũ theo dấu vết wizard để lại (`spa_partner_voucher_id`/tên dòng `'Redeem points'` + `spa_points_redeemed > 0`), **không** dùng config param hiện tại làm tiêu chí chính (chỉ log để soát tay các dòng chỉ khớp theo product id). Đã chạy thật trên bản sao `drlai`: gắn cờ đúng cho dòng SO của 8 đơn, 5 dòng hoá đơn/credit note, cảnh báo 1 dòng cần soát tay thủ công.
  7. 2 wizard chặn (raise UserError) nếu SO đã có `out_invoice` posted, để tránh dòng giảm giá bị tách thành credit note riêng gây trừ KPI hai lần.
  8. Giữ nguyên: tích điểm (đơn dùng điểm/voucher vẫn không được tích điểm — hành vi cũ ở `account_move.py:_spa_has_reward_line`); phiếu lương `done` không hồi tố.
- Consequences: HH của đơn dùng điểm/voucher giảm đúng phần đã giảm, khớp cách tính CK toàn đơn. Dòng HH lưu thêm `order_discount_share` (cột "CK HD" trên `spa.staff.payroll.commission.line`/report) để đối chiếu. Báo cáo doanh thu theo SP đổi số cho MỌI đơn có CK toàn đơn từ trước (nay net, khớp report theo đơn — trước đây lớn hơn). KPI/xếp hạng đổi cơ sở sang untaxed cho MỌI đơn có thuế (số liệu payroll draft sẽ khác khi tính lại; phiếu `done` giữ nguyên). Nhân bản (`copy()`) một SO đã dùng điểm/voucher sẽ bỏ các dòng đó và reset `spa_points_redeemed` (không tự trừ điểm lần 2 khi nhân bản).
- Alternatives considered: xem chi tiết & lý do loại trong review — tái dùng `is_global_discount` cho dòng điểm/voucher (loại: `_reverse_moves` xoá/sinh lại đúng 1 dòng CK theo `global_discount_share_percent`, sẽ gộp/mất dòng điểm; các field/report gắn với `is_global_discount` sẽ đổi nghĩa); nhận diện theo dấu `price_unit <= 0` (loại: dòng cọc/trả hàng/voucher tặng SP giá 0 cũng âm hoặc bằng 0, tiêu chí không ổn định); nhận diện qua config param `spa_loyalty.reward_product_id` lúc runtime (loại: đổi SP thưởng sau này sẽ phân loại sai dữ liệu cũ khi tính lại; chỉ dùng 1 lần trong migration); lưu sẵn (`store=True`) phần phân bổ trên `account.move.line` (loại: `_auto_init` sẽ tính lại toàn bảng lúc upgrade, và mỗi lần ghi bút toán lại kéo theo tính lại toàn bộ dòng cùng move — chọn helper không lưu, tính theo yêu cầu).
- Related files/modules: `spa/helper/order_discount.py` (mới), `spa/models/sale_order.py`, `spa/models/account_move.py`, `spa/models/spa_revenue_report_mixin.py`, `spa/models/spa_revenue_report.py`, `spa/models/spa_revenue_order_report.py`, `spa/wizards/spa_redeem_points_wizard.py`, `spa/wizards/apply_voucher_wizard.py`, `spa/migrations/1.0.4/`, `spa_staff_payroll/models/spa_staff_payroll.py`, `spa_staff_payroll/models/spa_staff_payroll_detail_line.py`, `spa_staff_payroll/models/spa_staff_payroll_commission_report.py`, `spa_staff_payroll/tests/test_spa_staff_payroll.py`, `spa/tests/test_spa_order_discount_line.py` (mới).

### [PAY-DEC-2026-09-03-01] Global discount prorated into commission base; card-return no longer double-clawed
- Date: 2026-09-03
- Status: accepted
- Context: điều tra (2 agent độc lập + 1 agent review, tự đọc code xác nhận) phát hiện 2 gap tài chính có thật: (1) CK toàn đơn (`is_global_discount`) bị skip khỏi hoa hồng nhưng KHÔNG được trừ vào subtotal các dòng SP còn lại — đóng "open risk" đã ghi ở PAY-DEC-2026-08-29-01/WORKLOG "HH ≠ KPI khi có CK toàn đơn"; (2) đơn "trả thẻ" (`spa.card.upgrade.wizard`, `upgrade_option='return'`) bị claw-back hoa hồng tính TRÙNG 2 lần vì lọt cả nhánh `_spa_sale_orders_settled_in_period` (SO thường) lẫn nhánh `_spa_so_linked_refunds_paid_in_period` (credit note liên kết).
- Decision:
  1. Thêm `_spa_global_discount_share_untaxed()` (helper riêng, cơ sở untaxed nhất quán — KHÔNG tái dùng `sale.order.line.global_discount_share` vì field đó trộn cơ sở thuế) trừ vào `price_subtotal` trước khi tính `commission_amount` trong `_spa_commission_detail_vals_for_sale_order`/`_for_invoice`. Áp dụng ngay, không có toggle bật/tắt (theo xác nhận của chủ dự án).
  2. Thêm field `sale.order.is_card_return_order` (đặt bởi wizard khi `upgrade_option='return'`), loại các đơn này khỏi `_spa_sale_orders_settled_in_period` — claw-back chỉ còn tính đúng 1 lần qua nhánh `so_refunds`.
  3. Sửa kèm 2 gap độc lập trong `spa_card_upgrade_wizard.py`: `credit_old_card` default ưu tiên giá đã bán thực tế trên `card.sale_order_line_id` (không phải giá pricelist hiện tại); `user_id` của đơn trả thẻ lấy theo salesperson đơn gốc (không phải `partner_id.user_id` hiện tại).
- Consequences: `commission_amount`/`price_subtotal` lưu trên `spa.staff.payroll.commission.line` cho các dòng có CK toàn đơn nay là giá trị NET (đã trừ CK); các phiếu lương `done` cũ giữ nguyên (không hồi tố, theo nguyên tắc "phiếu done không tự sửa"); double-clawback trả thẻ trong quá khứ (nếu có) KHÔNG được rà soát lại, chỉ chặn từ nay về sau.
- Alternatives considered: tái dùng `global_discount_share` có sẵn (loại vì lệch cơ sở thuế); tái dùng `is_global_discount`/`is_card_renewal` cho đơn trả thẻ thay vì field riêng (loại vì 2 field đó mang ý nghĩa khác, dễ gây nhầm lẫn nghiệp vụ — đúng lo ngại ban đầu khiến việc điều tra này được yêu cầu); rà soát/điều chỉnh thủ công phiếu lương done cũ (loại, theo quyết định người dùng).
- Related files/modules: `spa_staff_payroll.py` (`_spa_global_discount_share_untaxed`, `_spa_sale_orders_settled_in_period`, `_spa_commission_detail_vals_for_sale_order/_for_invoice`), `spa/models/sale_order.py` (`is_card_return_order`), `spa/wizards/spa_card_upgrade_wizard.py` (`default_get`, `action_confirm` nhánh `return`), `tests/test_spa_staff_payroll.py`
