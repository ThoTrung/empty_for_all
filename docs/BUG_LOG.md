# Booking Calendar Bug Log (Living Doc)

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

### [BC-BUG-2026-08-24-01] Create booking RPC crash: Datetime instance expected
- Date: 2026-08-24
- Reporter: user runtime
- Context (screen/model/action): form/calendar `web_save` tạo `spa.service.booking` có `staff_ids`
- Symptom: RPC_ERROR `AssertionError: Datetime instance expected` trong `user_slot_within_shift` → `fields.Datetime.context_timestamp`
- Reproduction steps: tạo đặt lịch từ UI, chọn NV, Lưu (vals `start_datetime`/`end_datetime` là chuỗi)
- Root cause: `web_save` gửi datetime dạng string; `_spa_prepare_outside_shift_create_vals` truyền raw string vào `user_slot_within_shift`, trong khi `context_timestamp` bắt buộc `datetime`
- Fix summary: coerce `start_dt`/`end_dt` bằng `fields.Datetime.to_datetime` trong `user_slot_within_shift`; chuẩn hóa luôn trong `_spa_prepare_outside_shift_create_vals`
- Files changed: `models/booking_shift_config.py`, `models/spa_service_booking.py`, `tests/test_booking_calendar.py`
- Test coverage: `test_create_booking_with_string_datetimes_like_web_save`, `test_user_slot_within_shift_string_matches_datetime`
- Regression risk: low (chỉ coerce kiểu; luật ca không đổi)
- Follow-up TODO: none
- Status: **fixed**

### [BC-BUG-2026-05-19-01] Single booking vanishes after moving start to next day (stale display_end)
- Date: 2026-05-19
- Reporter: user UAT
- Context (screen/model/action): form đặt lịch đơn, chưa gán NV, đổi `start_datetime` sang ngày kế tiếp rồi Lưu
- Symptom: không báo lỗi; booking biến mất khỏi lịch (record còn nhưng `end_datetime` vẫn ngày cũ → `end` < `start`, calendar không render)
- Reproduction steps: tạo booking đơn draft, không `staff_ids`, mở form, đổi Bắt đầu +1 ngày, Lưu; quan sát lịch ngày cũ
- Root cause: form `display_end_datetime` có `force_save="1"` gửi giá trị cũ cùng `write()`; `_inverse_display_end_datetime` ghim `end_datetime` ở ngày cũ trong khi `start_datetime` đã sang ngày mới
- Fix summary: giữ `display_end_datetime` + `force_save="1"`; `write()` bỏ display/end stale trên mọi form save (kể cả khi `duration` không có trong vals); calendar-only write giữ nguyên; `_inverse_display_end` bỏ qua end ngắn hơn start+duration; chọn thẻ pop display_end
- Files changed: `models/spa_service_booking.py`, `views/spa_service_booking_view.xml`, `tests/test_booking_calendar.py`
- Test coverage: `test_write_shift_start_to_next_day_single_booking_no_staff`
- Regression risk: low (chỉ khi `start_datetime` trong vals; kéo lịch vẫn qua `display_start` inverse)
- Follow-up TODO: none

### [BC-BUG-2026-05-08-03] View/test mismatch for `display_calendar_service_id`
- Date: 2026-05-08
- Reporter: AI audit
- Context (screen/model/action): booking view assertions in tests vs XML view fields
- Symptom: tests assert `display_calendar_service_id` is present in list/search/form while current view uses `product_id`.
- Reproduction steps: inspect `tests/test_booking_calendar.py` assertions and `views/spa_service_booking_view.xml`.
- Root cause: test expectation and current UI implementation are out of sync.
- Fix summary: decide canonical UI field, then align views and tests consistently.
- Files changed: pending
- Test coverage: affected by mismatch
- Regression risk: medium (false negatives/positives in suite)
- Follow-up TODO: add one integration assertion after alignment.

### [BC-BUG-2026-05-08-02] Undefined test fixture `self.card2`
- Date: 2026-05-08
- Reporter: AI audit
- Context (screen/model/action): booking chain test case
- Symptom: test references `self.card2` without creating fixture in `setUpClass`.
- Reproduction steps: search `self.card2` usage and compare with fixture setup.
- Root cause: missing fixture initialization.
- Fix summary: create `card2` in setup or replace with existing fixture.
- Files changed: pending
- Test coverage: blocked/incomplete for that test path
- Regression risk: medium (suite reliability reduced)
- Follow-up TODO: run full test file after fixture fix.

### [BC-BUG-2026-05-08-01] Broad exception swallowing in booking model helpers
- Date: 2026-05-08
- Reporter: AI audit
- Context (screen/model/action): calendar display inverse/text color helper methods
- Symptom: broad `except Exception` can hide real defects and silently fallback.
- Reproduction steps: inspect exception handling in `models/spa_service_booking.py`.
- Root cause: defensive catch-all without strict diagnostics.
- Fix summary: narrow exception types and add explicit logging context.
- Files changed: pending
- Test coverage: not explicit
- Regression risk: low/medium (debugging difficulty, hidden behavior drift)
- Follow-up TODO: add targeted tests for failure branches.

