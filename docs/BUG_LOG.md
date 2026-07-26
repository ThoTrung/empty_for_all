# Spa Staff Payroll Bug Log (Living Doc)

Use one section per bug. Keep entries short and reproducible.

## Template
### [BUG-ID] Short title
- Date:
- Reporter:
- Context (screen/model/action):
- Symptom:
- Reproduction steps:
- Root cause:
- Fix summary:
- Files changed:
- Test coverage:
- Regression risk:
- Follow-up TODO:

---

## Active Bugs

(none — PAY-BUG-2026-07-26-01/02 đã xử lý trong roadmap 2026-07-26; PAY-BUG-03 dayoff display-only giữ intentional)

---

## History

### [PAY-BUG-2026-07-26-01] Dual service payout paths both add to total (double-count)
- Date: 2026-07-26
- Status: **fixed**
- Fix summary: `_compute_amounts` bỏ `amount_service`; wizard không gọi `action_recompute_service_lines`; tab Dịch vụ tham khảo
- Test coverage: `test_no_double_count_service_and_ledger`

### [PAY-BUG-2026-07-26-02] Booking payroll flags not synced to treatment sessions
- Date: 2026-07-26
- Status: **fixed**
- Fix summary: create/write session copy từ booking; booking/line write sync session (skip nếu ledger trên phiếu done)
- Test coverage: `test_booking_flags_sync_to_session`

### [PAY-BUG-2026-07-26-03] Dayoff is display-only (no wage impact)
- Date: 2026-07-26
- Status: **accepted intentional** — help trên phiếu; điều chỉnh tay nếu cần
