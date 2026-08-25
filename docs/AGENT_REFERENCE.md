# Booking Calendar Module Reference (Living Doc)

> **Phiên làm việc chuẩn:** Áp dụng `docs/AGENT_SESSION_DEFAULTS.md` cho mọi task có thể liên quan `booking_calendar` và/hoặc `spa`. Người dùng thường chỉ gửi **mô tả nhiệm vụ**; quy trình chung đã gom vào file đó.

## 1) Business Scope
- Purpose: manage spa booking operations separated from core SPA module (calendar planning, staff capacity, recurring/composite bookings, reminder activities).
- Main roles: spa staff (daily scheduling), spa booking operator (assign performing staff + serve/complete), spa manager (configuration and catalog), spa customer (limited self-visibility via record rules).
- Expected outcomes: conflict-aware scheduling, predictable staff rotation, accurate booking completion linkage.

## 2) Technical Scope
- Main models:
  - core: `spa.service.booking`, `spa.service.booking.line`
  - supporting: `spa.booking.non_session_offering`, `booking.shift.config`, `booking.shift.config.line`, `booking.shift.week.template`, `booking.shift.week.template.line`
  - extensions: `spa.treatment.card` booking availability fields, `spa.treatment.session` booking link, `res.config.settings`, `product.template`
- Main wizards:
  - `spa.recurring.booking.wizard` for weekday-driven recurring booking generation.
  - `booking.shift.template.apply.wizard` for materializing week template → daily shift configs.
- Main controllers:
  - none in Python HTTP layer.
- Calendar frontend behavior:
  - custom JS renderer/controller/model patches and custom popover/height selector templates.

## 3) Data Model Notes
- Important fields:
  - chain display: `parent_booking_id`, `child_booking_ids`, `display_is_calendar_parent`, `display_start_datetime`, `display_end_datetime`
  - list display: `partner_customer_code` / `partner_phone` (related `res.partner.customer_code` / `phone`, not stored)
  - staffing/capacity: `staff_ids`, `staff_outside_shift`, `staff_outside_shift_user_ids` (per-NV audit khi multi-staff), `staff_level_filter`, capacity percent checks
  - menu calendar board: `booking_board` (`specialist` | `doctor`) — Selection ẩn trên UI; domain menu Doctor/Specialist; default từ context `default_booking_board` khi tạo từ menu tương ứng (model default = `specialist`)
  - completion delegation: `completion_res_model_id`, `completion_res_id`
  - recurring setup: `recurring_*` fields, `recurring_copy_staff`, parent-child recurring links
- Compute/store design:
  - numerous computed fields for calendar rendering and booking aggregation; some are stored for fast search/filter.
  - Menu Doctor/Specialist **không** còn dựa trên cấp độ NV/product (`is_doctor_route` đã gỡ); lọc thẻ/NV khi tạo vẫn dùng context `spa_allowed_staff_levels`.
- Constraints:
  - datetime ordering, staff capacity, shift windows **when day roster published** (`booking.shift.config` with lines), `staff_outside_shift` override, completion target validity, bed conflict prevention.
- Side-effect points:
  - booking create/write/unlink invalidates treatment card booking availability cache fields.

## 4) View Architecture
- Main views:
  - `views/spa_service_booking_view.xml` (search/calendar/tree/form/actions)
  - tree `view_spa_service_booking_tree` (`default_order="start_datetime desc, id desc"`; `name` + `end_datetime` optional hide; `partner_customer_code` before `partner_id`, `partner_phone` after). Operator tree primary-inherits this arch (Lịch phục vụ).
  - `views/spa_service_booking_line_view.xml` (line-level assign-staff modal action)
  - `views/booking_shift_config_views.xml` (shift setup modal)
- Inherited xpaths:
  - `views/res_config_settings_views.xml` injects booking-related settings into SPA settings.
  - `views/spa_treatment_session_booking_views.xml` adds booking reference to treatment session form.
- Calendar color/filter logic:
  - event color fields are computed in model and normalized in JS layer for display/readability.
  - Extension (`spa_staff_payroll`): khi `spa_payroll_customer_requested` (booking hoặc bất kỳ line) và `state` ∈ {draft, confirmed}, màu HEX ICP `spa.booking_calendar_hex_color_customer_requested` (default `#FF8C00`) ghi đè state + draft-special; trạng thái khác giữ logic cũ.
- Calendar event title (`calendar_event_title` / `create_name_field`):
  - format: `(staff nicknames) customer_code Name (phone) [ - note] service_internal_ref[+ ...]`
  - mã KH (`res.partner.customer_code`) luôn đứng trước tên KH khi có mã.

## 5) Security Model
- Access rights:
  - `spa.group_spa_staff`: CRUD booking + booking lines + recurring wizard, read offerings.
  - `spa.group_spa_manager`: CRUD shift config and offering management.
  - `spa.group_spa_customer`: read-only booking/line/offering views.
  - `spa.group_spa_booking_operator`: read+write booking/line (write whitelist: performing staff only); read offering; menu **Lịch phục vụ**; serve/complete via sudo transitions (no create/unlink, no confirm/cancel).
- Record rules:
  - customer can only see own/commercial-partner booking tree and related lines; offerings must be active.
  - booking operator (without spa staff): `state in (confirmed, doing, done)` on booking + lines.
- Sensitive risk notes:
  - selected flows use `sudo()` for config/activity convenience; verify security impact whenever extending reminder/auto-write paths.
  - operator `action_doing`/`action_done` use `sudo()` + context `spa_booking_operator_transition` after staff validation.

## 6) Main Workflows
- Booking lifecycle:
  - trigger: create/edit booking from calendar/form.
  - methods: duration/end compute, chain re-link, capacity/shift checks, composite sync.
  - side effects: card availability recalculation and potential chain propagation.
  - `action_doing` requires Nhân viên thực hiện (`staff_ids` or any line `staff_id`) for all users.
- Recurring scheduling:
  - trigger: recurring wizard or booking recurring actions.
  - methods: generate weekday bookings, cleanup future unused recurring children, align dates.
  - side effects: may create or remove linked future bookings based on remaining sessions.
- Completion flow:
  - trigger: `action_done`.
  - methods: resolve completion target and call `spa_complete_booking`.
  - side effects: treatment session completion or non-session offering completion updates.
- Reminder cron:
  - trigger: scheduled cron job.
  - methods: find near-term draft bookings and create staff activities.
  - side effects: marks `reminder_sent` to avoid duplicate reminders.

## 7) Dependencies
- Declared in `__manifest__.py`: `spa`, `mail`, `web`.
- Optional downstream: `spa_staff_payroll` (depends `booking_calendar`) extends calendar colors + constrains staff khi «Khách chủ động đặt NV».
- Read-only staff: `spa.group_spa_staff_readonly` nhận ACL đọc trên `spa.service.booking` / line / non-session offering (mirror staff), không có quyền wizard recurring; nút chuyển trạng thái trên form gắn `groups=\"spa.group_spa_staff\"`; `set_calendar_display_config` chặn user chỉ đọc.
- Booking operator: `spa.group_spa_booking_operator` — menu Lịch phục vụ; form `edit=1` chỉ NV thực hiện; nút Phục vụ/Hoàn thành; không create/unlink; record rule state confirmed/doing/done; không dùng chung Read-only.
- Cross-module assumptions:
  - relies heavily on `spa` models/fields (`spa.treatment.card`, staff levels, beds, partner/service structures).
- Hidden dependency caution:
  - frontend patches depend on web calendar internals; verify behavior on Odoo minor upgrades.

## 8) Tests
- Existing tests:
  - `tests/test_booking_calendar.py` (large TransactionCase suite)
  - `tests/test_booking_operator.py` (Spa Booking Operator ACL/serve/complete + performing-staff write)
  - `static/tests/booking_calendar_color_tests.js` (frontend color logic)
- Covered scenarios:
  - shift availability + outside-shift flag (Phase 1 2026-08-22), RPC string datetime create (`web_save`), staff rotation, composite line sync, non-session completion, color behavior, tree default_order + Mã KH/sdt columns.
- Missing high-risk coverage:
  - recurring inline action (`action_confirm_recurring`) edge cases
  - record-rule regression tests for customer visibility
  - reminder cron idempotency/timezone behavior
  - drag/drop inverse field behavior
- Run tests:
  - `odoo-bin -d <db> -i booking_calendar --test-enable --stop-after-init`

## 9) Known Pitfalls
- View/test drift:
  - symptom: tests may assert fields not present in current view arch.
  - root cause: tests and XML evolved out of sync.
  - safe fix pattern: align intended UX first, then update either view or tests accordingly.
- Prototype patch fragility:
  - symptom: calendar behavior breaks after web framework updates.
  - root cause: patching internal renderer/controller/model methods.
  - safe fix pattern: re-validate custom JS patches on each Odoo upgrade and keep guard by `resModel`.
- Broad exception swallowing in utility methods:
  - symptom: hidden runtime issues with incomplete diagnosis.
  - root cause: broad `except Exception` with fallback behavior.
  - safe fix pattern: narrow exception types and add logging context.
- RPC datetime strings vs `context_timestamp`:
  - symptom: `AssertionError: Datetime instance expected` when creating a booking from form/calendar with staff assigned.
  - root cause: `web_save` sends `start_datetime`/`end_datetime` as `"YYYY-mm-dd HH:MM:SS"`; `fields.Datetime.context_timestamp` requires a `datetime`.
  - safe fix pattern: coerce with `fields.Datetime.to_datetime` in `user_slot_within_shift` (and any create/write helper that forwards vals datetimes into that API).

## 10) Change Protocol For New Agents
0. Follow repo-wide session contract in `docs/AGENT_SESSION_DEFAULTS.md` (read order, skill, dependency check, worklog updates).
1. Read this file, then `BUG_LOG.md`, `DECISIONS.md`, `WORKLOG.md`.
2. Validate shift/capacity and recurring side effects whenever modifying booking writes.
3. Keep calendar XML/xpaths minimal and verify JS patch compatibility.
4. For security-sensitive updates, re-check customer record rules and `sudo()` usage paths.
5. Add/update tests for any change in chain, recurring, capacity, or reminder logic.
6. Mandatory dependency impact check before closing task:
   - list all dependents of changed code (booking chain methods, calendar views, JS patches, cron, tests).
   - verify contract compatibility (fields/methods/view XML ids/calendar behavior assumptions).
   - run targeted regression tests for affected flows; if missing, record explicit manual checks.
   - update all dependent code in same task when intentional contract changes are introduced.
