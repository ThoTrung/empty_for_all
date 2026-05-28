# Booking Calendar Worklog (Session Handoff)

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

### 2026-05-27 - Booking: chỉ hiển thị mã tham chiếu nội bộ cho dịch vụ
- Goal: trong màn Đặt lịch, hiển thị dịch vụ bằng `default_code` (mã tham chiếu nội bộ) thay vì `code - name`.
- Changes made:
  - calendar title (`calendar_event_title`) chỉ ghép mã tham chiếu nội bộ (fallback tên nếu thiếu mã).
  - thêm field hiển thị `product_internal_ref`/`product_internal_ref` (line) và dùng trong search/tree/modal để chỉ hiện mã, không cần can thiệp `product.product.name_get`.
- Files touched:
  - `custom_addons/booking_calendar/models/spa_service_booking.py`
  - `custom_addons/booking_calendar/models/spa_service_booking_line.py`
  - `custom_addons/booking_calendar/views/spa_service_booking_view.xml`
  - `custom_addons/booking_calendar/views/spa_service_booking_line_view.xml`
  - `custom_addons/booking_calendar/tests/test_booking_calendar.py`
- Validation done:
  - `python3 -m compileall -q` các file đã sửa.
- Dependency impact check:
  - Dependents reviewed: calendar view uses `create_name_field="calendar_event_title"`, list/search/tree product fields, reminder activity (không đổi), các JS patches không phụ thuộc format service label.
  - Contract compatibility result: không đổi field/model/XML id; chỉ thêm field compute/related dùng cho hiển thị và search domain.
  - Regression tests/manual checks run: cập nhật assertions liên quan `calendar_event_title` trong `test_booking_calendar.py`; manual UI: mở lịch đặt → tiêu đề chỉ còn mã (vd `C005488`).
- Open risks: sản phẩm không có `default_code` sẽ fallback về tên để tránh trống.
- Next suggested steps: nếu cần áp dụng thêm cho chỗ khác (nhắc lịch/activity hoặc report), thêm context tương tự hoặc chuẩn hoá formatter.

### 2026-05-19 - Fix booking disappears when shifting start to next day (single booking)
- Goal: sửa lỗi đặt lịch đơn (chưa NV) đổi Bắt đầu sang ngày sau thì mất trên lịch; **giữ** `force_save` trên `display_end_datetime` (regression duration 60p).
- Changes made:
  - reproduce trên drlai: `start` ngày mới + `display_end` cũ (force_save) → `end < start`, calendar ẩn event
  - `_sanitize_schedule_write_vals`: đổi `start_datetime` → bỏ display/end cũ; có `duration` → bỏ display/end stale (duration thắng, không về 60p)
  - **Giữ** form `display_end_datetime` + `force_save="1"` như trước
  - create: sanitize khi có `duration`; sau create gọi `_compute_display_datetimes()`
  - tests: shift ngày, duration 90p Form/write, stale display_end create/write
- Files touched:
  - `custom_addons/booking_calendar/models/spa_service_booking.py`
  - `custom_addons/booking_calendar/views/spa_service_booking_view.xml`
  - `custom_addons/booking_calendar/tests/test_booking_calendar.py`
  - `custom_addons/booking_calendar/docs/BUG_LOG.md`
- Validation done:
  - shell Form 90p + shift ngày; API write shift + stale display_end
  - 6 regression tests pass (tag `.test_create_booking_keeps_duration_when_stale_display_end_datetime_posted`, `.test_write_booking_keeps_duration_when_stale_end_datetime_posted`, `.test_write_shift_*`, `.test_form_*`)
- Dependency impact check:
  - Dependents reviewed: calendar (`display_*`), form save, `write`/`_inverse_display_*`, chain parent form end display
  - Contract compatibility: giữ field names; chỉ bỏ nhận stale display payload khi đổi start
  - Regression tests/manual checks run: `test_write_shift_start_to_next_day_single_booking_no_staff`; manual UI: sửa Bắt đầu +1 ngày, mở lịch đúng ngày
- Open risks: booking đã lưu trước fix với `end < start` cần sửa tay hoặc script one-off
- Next suggested steps: `-u booking_calendar` trên DB UAT; kiểm tra vài record draft bị lệch end/start nếu user báo vẫn mất

### 2026-05-09 - post-UAT correction for readonly booking scope gate
- Goal: ensure readonly user sees exactly own assigned bookings in drlai.
- Changes made:
  - switched booking readonly rules to global conditional gate and included legacy `staff_id` in domain.
- Files touched:
  - `custom_addons/booking_calendar/security/staff_readonly_booking_security.xml`
- Validation done:
  - lints clean.
- Dependency impact check:
  - Dependents reviewed: booking search/list/calendar and line reads for readonly users.
  - Contract compatibility result: additive domain logic only.
  - Regression tests/manual checks run: pending target DB retest.
- Open risks:
  - records without any staff assignment intentionally remain invisible.
- Next suggested steps:
  - validate with composite and single-staff bookings on drlai.


### 2026-05-09 - Readonly booking visibility narrowed to assigned staff only
- Goal: readonly staff only sees bookings where they are assigned (direct or any composite line).
- Changes made:
  - added record rules for readonly group on `spa.service.booking` and `spa.service.booking.line` using domains on `staff_ids` / `booking_line_ids.staff_id`.
  - added regression tests for direct-assigned visibility and composite-line assignment visibility.
- Files touched:
  - `custom_addons/booking_calendar/security/staff_readonly_booking_security.xml`
  - `custom_addons/booking_calendar/__manifest__.py`
  - `custom_addons/booking_calendar/tests/test_staff_readonly_observer.py`
- Validation done:
  - `python3 -m compileall -q` for updated tests; lints clean.
- Dependency impact check:
  - Dependents reviewed: booking tree/form/calendar reads and one2many line fetches under readonly group.
  - Contract compatibility result: no model/view contract change; additive rule-only behavior.
  - Regression tests/manual checks run: new readonly visibility tests added.
- Open risks:
  - bookings without any assigned staff become invisible for readonly users by design.
- Next suggested steps:
  - verify business acceptance on composite bookings with mixed staff lines in production-like data.

### 2026-05-09 - Spa Staff readonly trên đặt lịch + cấu hình lịch
- Goal: khớp `spa.group_spa_staff_readonly` cho booking_calendar (ACL + UI + RPC).
- Changes made:
  - `security/ir.model.access.xml`: ACL read-only cho booking/booking.line/non_session_offering.
  - Menu đặt lịch mở thêm cho readonly như nhân viên.
  - `views/spa_service_booking_view.xml`: nút trạng thái/recurring/ghép dịch vụ/Chọn NV gắn `spa.group_spa_staff`; nút navig cha/con cho phép readonly.
  - `models/spa_service_booking.py`: `set_calendar_display_config` gọi `spa_staff_raise_if_readonly_observer()`.
  - `models/spa_service_booking_line.py`: RPC modal chọn NV chặn readonly.
  - Test `tests/test_staff_readonly_observer.py`.
- Validation done:
  - `python3 -m compileall …` các file đã chỉnh; post-install `--test-enable` phụ thuộc DB đã có module spa/booking_calendar cài đầy đủ như WORKLOG spa.
- Dependency impact check:
  - Dependents reviewed: SPA menu parent, frontend lịch (RPC set_calendar_display_config), test suite đặt lịch.
  - Contract compatibility: giữ XML id/menu; chỉ điều kiện `groups` và model methods.
  - Regression tests/manual checks run: compileall + (trên DB đầy đủ) `--test-enable` tag `booking_calendar`,`spa_security`.
- Next suggested steps: chạy `test_booking_calendar` đầy bộ sau khi sửa `BC-BUG view/test mismatch`.

### 2026-05-08 - Project memory maintenance sync
- Goal: apply start-of-task memory protocol before coding and capture current constraints.
- Changes made:
  - read root `AGENTS.md` and all SPA/booking_calendar memory docs (`AGENT_REFERENCE.md`, `BUG_LOG.md`, `DECISIONS.md`, `WORKLOG.md`)
  - refreshed active constraints/risks for upcoming implementation tasks
- Files touched:
  - `custom_addons/spa/docs/WORKLOG.md`
  - `custom_addons/booking_calendar/docs/WORKLOG.md`
- Validation done:
  - confirmed current booking_calendar memory reflects model/view/security/test risk areas
- Dependency impact check:
  - Dependents reviewed: none impacted (memory-only update, no model/view/action/cron/test/asset contract changed)
  - Contract compatibility result: unchanged
  - Regression tests/manual checks run: not required for documentation-only update
- Open risks:
  - existing unresolved bugs remain as listed in `BUG_LOG.md` (test fixture drift, view/test mismatch, broad exception handling risk)
- Next suggested steps:
  - apply one scoped bug fix (tests first), then record dependent checks and targeted regressions

### 2026-05-08 - Deep module audit for long-term agent memory
- Goal: build complete architecture/workflow/security/test memory for booking_calendar.
- Changes made:
  - reviewed manifest/models/wizards/views/security/assets/tests
  - documented module structure, key design decisions, and critical workflows
  - recorded confirmed issues and testing gaps for follow-up
- Files touched:
  - `custom_addons/booking_calendar/docs/AGENT_REFERENCE.md`
  - `custom_addons/booking_calendar/docs/BUG_LOG.md`
  - `custom_addons/booking_calendar/docs/DECISIONS.md`
  - `custom_addons/booking_calendar/docs/WORKLOG.md`
- Validation done:
  - cross-checked test/view mismatch and undefined fixture findings with source files
  - verified dependency/data/assets/security declarations in manifest/XML
- Open risks:
  - test reliability issues (`self.card2` fixture and view-field assertion drift)
  - frontend patch fragility on web/calendar internals
  - broad exception handling masking errors
- Next suggested steps:
  - fix broken/stale tests first
  - align calendar display field contract between model/view/tests
  - add regression tests for recurring-inline flow and customer security rules

