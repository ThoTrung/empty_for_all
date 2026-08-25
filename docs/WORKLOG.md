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

### 2026-08-24 - Fix web_save create crash (Datetime instance expected)
- Goal: Sửa RPC_ERROR khi tạo đặt lịch từ UI (`web_save` gửi datetime dạng chuỗi).
- Changes made:
  - `user_slot_within_shift` coerce `start_dt`/`end_dt` qua `fields.Datetime.to_datetime` trước `context_timestamp`.
  - `_spa_prepare_outside_shift_create_vals` chuẩn hóa start/end trước khi lọc NV ngoài ca.
  - Tests: create với string datetime (giống web_save); parity string vs datetime cho helper ca.
- Files touched: `models/booking_shift_config.py`, `models/spa_service_booking.py`, `tests/test_booking_calendar.py`, `docs/BUG_LOG.md`, `docs/WORKLOG.md`, `docs/AGENT_REFERENCE.md`.
- Validation done: `./venv/bin/python3 ./odoo/odoo-bin -c ./conf/odoo_dev.conf -d drlai --http-port=8091 --test-enable --stop-after-init --test-tags=.test_create_booking_with_string_datetimes_like_web_save,.test_user_slot_within_shift_string_matches_datetime` → **0 failed, 0 error(s) of 2 tests**.
- Dependency impact check:
  - Dependents reviewed: `_spa_staff_outside_shift_users`, shift constraint, `get_available_staff_ids`, line onchange `user_slot_within_shift`; không đụng `spa` / `spa_staff_payroll`.
  - Contract compatibility result: cùng chữ ký `user_slot_within_shift(user, start_dt, end_dt)`; nhận string an toàn hơn; luật ca không đổi.
  - Regression tests/manual checks run: 2 targeted tests, 0 failed / 0 errors on `drlai`.
- Open risks: none for this crash; UI smoke trên form/calendar vẫn nên xác nhận sau reload.
- Next suggested steps: tạo lịch từ calendar/form trên `drlai`, chọn NV trong ca, Lưu — không RPC_ERROR, không bắt tick ngoài ca.

### 2026-08-22 - Phase 1.1 + Phase 2a/2b (critique plan)
- Goal: Close Phase 1 gaps (per-user outside-shift audit, write sync, availability refactor); add week shift template materialize; recurring staff copy with fallback.
- Changes made:
  - `staff_outside_shift_user_ids` M2M + `_spa_sync_staff_outside_shift_flags` on write; create auto-fills M2M when boolean set.
  - `get_available_staff_ids` uses `user_slot_within_shift` (no duplicate inline logic).
  - `booking.shift.week.template` + lines + apply wizard (skip existing default, optional overwrite).
  - `recurring_copy_staff` + `_create_recurring_child_booking` savepoint fallback without staff on ValidationError.
  - Form: M2M audit field, composite tree `staff_outside_shift`, menu «Mẫu ca tuần».
  - Tests: multi-staff mixed, composite line flag, write reschedule, template skip/overwrite, recurring copy; fixed 5 pre-existing suite failures.
- Files touched: `models/spa_service_booking.py`, `models/booking_shift_week_template.py`, views, security, `tests/test_booking_calendar.py`, docs.
- Validation done: `-u booking_calendar --test-enable` on `drlai` → **118 booking_calendar tests, 0 failed / 0 errors** (189 total with dependents).
- Dependency impact check:
  - Dependents reviewed: operator write whitelist extended for M2M; bundled form save strips placeholder lines before INSERT.
  - Contract compatibility result: additive fields; template wizard manager-only write.
  - Regression tests/manual checks run: full suite green.
- Open risks: apply template default skips manual days — operators must tick overwrite intentionally; recurring staff copy drops staff silently on conflict (chatter summary for skipped dates).
- Next suggested steps: optional calendar button «Áp dụng mẫu ca»; Phase 2b wizard summary UI for skipped staff dates.

### 2026-08-22 - Phase 1: shift gate vs staff assignment
- Goal: Fix OT / future booking blocked when no daily shift config; allow controlled outside-shift assignment.
- Changes made:
  - `booking.shift.config`: `shift_config_applies_for_date`, `user_slot_within_shift`.
  - `spa.service.booking`: `staff_outside_shift`; constraint only when day roster published; operator may set flag.
  - `spa.service.booking.line`: `staff_outside_shift` per step.
  - `get_available_staff_ids`: skip shift filter when no published roster for day/prev day.
  - Form views + 5 tests.
- Files touched: `models/booking_shift_config.py`, `models/spa_service_booking.py`, `models/spa_service_booking_line.py`, views, `tests/test_booking_calendar.py`, `docs/DECISIONS.md`, `docs/WORKLOG.md`, `docs/AGENT_REFERENCE.md`.
- Validation done: `-u booking_calendar --test-enable` on `drlai` — 5 new tests run clean; 3 pre-existing failures unrelated (draft color, list view column, senior filter).
- Dependency impact check:
  - Dependents reviewed: operator write whitelist, composite line modal, payroll (no coupling), recurring (unchanged).
  - Contract compatibility result: additive field + relaxed constraint when no roster; stricter message when roster exists.
  - Regression tests/manual checks run: full booking_calendar suite (111 tests).
- Open risks: days without roster allow any internal staff (level/capacity only); operator can tick outside-shift flag.
- Next suggested steps: Phase 2 week template materialize; optional online-booking channel hard gate.

### 2026-08-20 - Prod ZNS whitelist 1–2 SĐT (runbook)
- Goal: Cron/enqueue/send tôn trọng whitelist khi smoke production.
- Changes made: none in booking_calendar source.
- Files touched: none in this module.
- Validation done: `--test-tags=/spa_zalo_oa` trên `drlai` → **0 failed / 25 tests**.
- Dependency impact check:
  - Dependents reviewed: `spa.service.booking._cron_send_zalo_reminders` không đổi chữ ký; whitelist vẫn lọc trước enqueue.
  - Contract compatibility result: no booking_calendar XML/field change.
  - Regression tests/manual checks run: TestZaloOa 25 tests, 0 failed.
- Open risks: B8 tắt whitelist chỉ sau khi B7.3 ổn — không làm lúc deploy.
- Next suggested steps: `-u spa_zalo_oa` trên prod; checklist ACTIVATION.md B7.

### 2026-08-20 - Zalo OA ZNS go-live hardening (spa_zalo_oa)
- Goal: Nhắc lịch ZNS chỉ `confirmed`; hủy/đổi giờ hủy tin queued; hiện `zalo_reminder_sent` trên form.
- Changes made: none in booking_calendar source; inherit form từ `spa_zalo_oa`.
- Files touched: none in this module.
- Validation done: `--test-tags=/spa_zalo_oa` trên `drlai` → **0 failed / 23 tests** (2026-08-20).
- Dependency impact check:
  - Dependents reviewed: `view_spa_service_booking_form` xpath `partner_id`; `write()`/`state=cancel`/`start_datetime` — additive hook trong `spa_zalo_oa`.
  - Contract compatibility result: không đổi XML id / field booking_calendar; `reminder_sent` (NV) không đụng.
  - Regression tests/manual checks run: TestZaloOa 23 tests, 0 failed.
- Open risks: `write({state: confirmed})` trong test không qua UI Xác nhận.
- Next suggested steps: `-u spa_zalo_oa`; checklist ACTIVATION.md.

### 2026-08-19 - Tree Lịch phục vụ: sort desc + Mã KH/sdt
- Goal: Tree booking sắp xếp giảm dần theo giờ bắt đầu; ẩn mặc định Mã đặt lịch và Kết thúc; hiện Mã KH trước / sdt sau cột Khách hàng.
- Changes made: related `partner_customer_code` / `partner_phone`; tree `default_order="start_datetime desc, id desc"`; `name`/`end_datetime` optional hide.
- Files touched: `models/spa_service_booking.py`, `views/spa_service_booking_view.xml`, `tests/test_booking_calendar.py`, docs.
- Validation done: `--test-tags=/booking_calendar:TestBookingCalendar.test_tree_view_default_order_and_optional_columns,/booking_calendar:TestBookingCalendar.test_partner_customer_code_and_phone_related` trên DB `drlai`.
- Dependency impact check:
  - Dependents reviewed: operator tree primary inherit; `spa_staff_payroll` không inherit tree; operator write whitelist không đụng related readonly.
  - Contract compatibility result: additive fields + view attrs; XML ids / `_order` model không đổi.
  - Regression tests/manual checks run: TestBookingCalendar tree + related methods.
- Open risks: browser localStorage có thể giữ cột optional cũ — hard refresh / ẩn danh nếu UI chưa đổi.
- Next suggested steps: `-u booking_calendar` trên `drlai`; mở Lịch phục vụ list (cửa sổ ẩn danh nếu cột cũ còn hiện).

### 2026-08-19 - Operator được sửa Nhân viên thực hiện
- Goal: Spa Booking Operator mở form chi tiết và sửa NV thực hiện (đơn + gộp), không CRUD/Xác nhận.
- Changes made: ACL write booking/line; write whitelist `staff_ids` / line `staff_id`; tách sync duration vs staff trên line; form operator `edit=1` + field khác readonly; calendar date_start readonly; ACL đọc `booking.shift.config` cho Staff + Operator (constraint ca khi đổi NV).
- Files touched: `security/ir.model.access.xml`, `models/spa_service_booking.py`, `models/spa_service_booking_line.py`, `views/spa_service_booking_view.xml`, `tests/test_booking_operator.py`, docs.
- Validation done: `--test-tags=/booking_calendar:TestBookingOperator` trên DB `drlai`.
- Dependency impact check:
  - Dependents reviewed: `spa_staff_payroll` inherit form operator (readonly flag lương); `action_doing`/`action_done` sudo không đổi; readonly observer không đổi.
  - Contract compatibility result: additive write whitelist; create/unlink/confirm/cancel vẫn chặn.
  - Regression tests/manual checks run: TestBookingOperator.
- Open risks: gán Operator+Staff vẫn full Staff (by design).
- Next suggested steps: `-u spa,booking_calendar,spa_staff_payroll`; UI Lịch phục vụ đổi NV rồi Lưu, rồi Phục vụ.

### 2026-08-03 - Note: spa loyalty pre-deploy check (no code change)
- Goal: Confirm no booking impact before spa loyalty cancel prod deploy.
- Changes made: none
- Files touched: none
- Validation done: n/a
- Dependency impact check:
  - Dependents reviewed: booking không gọi spa loyalty cancel hooks.
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
  - Dependents reviewed: không đọc spa.loyalty.ledger cancel hooks.
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
  - Dependents reviewed: không phụ thuộc ledger loyalty spa.
  - Contract compatibility result: no impact.
  - Regression tests/manual checks run: none
- Open risks: none
- Next suggested steps: none

### 2026-07-26 - Spa Booking Operator + Lịch phục vụ
- Goal: Nhóm/màn nhân viên nhận lịch: confirmed/doing/done; Phục vụ/Hoàn thành; bắt buộc Nhân viên thực hiện; không CRUD.
- Changes made: group + ACL + record rule; sudo transitions; menu/action/views operator; popover JS; tests.
- Files touched: spa groups/ACL/`res_users`/`custome_menu`/menu; booking_calendar security/model/views/menu/popover/tests/docs.
- Validation done: `--test-tags=/booking_calendar:TestBookingOperator` trên DB `drlai` — 0 fail.
- Dependency impact check:
  - Dependents reviewed: `spa_staff_payroll` (không đổi); completion `spa_complete_booking`; readonly rules vẫn độc lập; menus staff/readonly không đổi action cũ.
  - Contract compatibility result: additive group/action; `action_doing` thêm validate NV cho mọi user.
  - Regression tests/manual checks run: TestBookingOperator.
- Open risks: gán nhầm Operator + Staff sẽ bỏ record-rule gate (by design).
- Next suggested steps: tạo user kiosk chỉ Operator; `-u spa,booking_calendar`; UI Lịch phục vụ.

### 2026-07-26 - Ẩn booking_board trên UI đặt lịch
- Goal: Không cho chọn «Bảng đặt lịch» trên form/list/search; chỉ gán từ menu.
- Changes made: form `invisible="1"`; gỡ khỏi tree/search filters/group_by; cập nhật test/docs.
- Files touched: `views/spa_service_booking_view.xml`, `tests/test_booking_route_menu_domains.py`, docs.
- Validation done: view arch ẩn field; domain/action context giữ nguyên.
- Dependency impact check:
  - Dependents reviewed: actions Doctor/Specialist vẫn dùng `booking_board` + `default_booking_board`.
  - Contract compatibility result: field vẫn tồn tại; chỉ ẩn UI.
  - Regression tests/manual checks run: assertion form có `booking_board` invisible.
- Open risks: không đổi board thủ công sau khi tạo (đúng yêu cầu).
- Next suggested steps: reload UI, xác nhận field không hiện trên form.

### 2026-07-26 - booking_board thay is_doctor_route
- Goal: Phân chia menu Đặt lịch (Bác sĩ)/(Chuyên viên) bằng Selection «Bảng đặt lịch», không phụ thuộc cấp độ NV/dịch vụ.
- Changes made:
  - Thêm `booking_board` (specialist/doctor, default specialist); xóa compute `is_doctor_route`.
  - Action domains/context `default_booking_board`; form ẩn / tree+search không hiện.
  - Copy board khi tạo recurring child và composite child.
  - Pre-migrate 17.0.1.1.0 từ `is_doctor_route`.
- Files touched:
  - `models/spa_service_booking.py`
  - `views/spa_service_booking_view.xml`
  - `__manifest__.py`
  - `migrations/17.0.1.1.0/pre-migrate.py`
  - `tests/test_booking_calendar.py`, `tests/test_booking_route_menu_domains.py`
  - `docs/DECISIONS.md`, `AGENT_REFERENCE.md`, `WORKLOG.md`
- Validation done: unit tests booking_board + action domains — `0 failed, 0 error(s)` với `--test-tags=/booking_calendar:TestBookingRouteMenuDomains,booking_calendar.test_booking_board_from_context_and_independent_of_staff_level` trên `drlai`.
- Dependency impact check:
  - Dependents reviewed: `spa_staff_payroll` (không dùng `is_doctor_route`); spa staff level vẫn dùng cho domain chọn NV/thẻ; menus/actions trong booking_calendar.
  - Contract compatibility result: breaking field rename `is_doctor_route` → `booking_board` (có chủ đích + migrate); XML action domains đổi; `spa_allowed_staff_levels` giữ nguyên.
  - Regression tests/manual checks run: `TestBookingRouteMenuDomains` + `test_booking_board_from_context_and_independent_of_staff_level` (pass).
- Open risks: child recurring cũ migrate theo từng record; user có thể đổi board thủ công trên form.
- Next suggested steps: restart/reload server `drlai`; kiểm UI hai menu calendar.

### 2026-07-26 - Spa display Drlai + clinic_only (no booking code change)
- Goal: Ghi nhận dependency: spa đổi display name → Drlai và thêm `group_clic_clinic_only`.
- Changes made: none in booking_calendar.
- Files touched: `docs/WORKLOG.md` only.
- Validation done: n/a (spa-side tests).
- Dependency impact check:
  - Dependents reviewed: booking menus under `spa.menu_spa_root`; không gắn `group_clic_clinic_only`.
  - Contract compatibility result: XML ids spa không đổi; user clinic_only không thấy booking menus trừ khi có group spa staff.
  - Regression tests/manual checks run: none in this module.
- Open risks: none for booking.
- Next suggested steps: none.

### 2026-07-22 - (spa) Tab Thông tin khám: CCCD / vị trí / phân tích da — không đụng booking_calendar
- Goal: Ghi nhận dependency check khi spa đổi reception exam fields + exam sheet print.
- Changes made: none in booking_calendar code.
- Files touched: `docs/WORKLOG.md` only.
- Validation done: n/a (spa-only).
- Dependency impact check:
  - Dependents reviewed: `spa_service_booking` / calendar views — không đọc `lesion_location` / `free_skin_analysis` / exam sheet placeholders.
  - Contract compatibility result: compatible; no booking_calendar contract change.
  - Regression tests/manual checks run: none required for booking_calendar.
- Open risks: none.
- Next suggested steps: none.

### 2026-07-14 - Calendar màu cam khi «Khách chủ động đặt NV» (spa_staff_payroll)
- Goal: tick `spa_payroll_customer_requested` → lịch cam (configurable) ở draft/confirmed; trạng thái khác giữ logic cũ; bắt buộc có staff khi tick.
- Changes made:
  - Override `_compute_state_calendar_hex_*` + `_compute_draft_special_colors` trong `spa_staff_payroll`.
  - ICP/settings: `spa.booking_calendar_hex_color_customer_requested` (default `#FF8C00`) + text color.
  - Constrains booking `staff_ids` / line `staff_id` khi flag True; form `required` attrs.
- Files touched:
  - `custom_addons/spa_staff_payroll/models/spa_booking_payroll_fields.py`
  - `custom_addons/spa_staff_payroll/models/res_config_settings.py`
  - `custom_addons/spa_staff_payroll/views/spa_booking_payroll_views.xml`
  - `custom_addons/spa_staff_payroll/views/res_config_settings_views.xml`
  - `custom_addons/spa_staff_payroll/tests/test_spa_staff_payroll.py`
  - `custom_addons/spa_staff_payroll/__manifest__.py`, `models/__init__.py`
  - `booking_calendar/docs/WORKLOG.md`, `DECISIONS.md`, `AGENT_REFERENCE.md`
- Validation done: unit tests payroll (color + staff constraint); xem lệnh trong phản hồi task.
- Dependency impact check:
  - Dependents reviewed: calendar JS `applySpaBookingEventColors` (vẫn đọc `state_*` / `draft_special_*`); form booking/line payroll inherit; Spa settings màu lịch.
  - Contract compatibility result: additive ICP + override compute trong downstream module; không đổi XML id/field calendar core.
  - Regression tests/manual checks run: tests mới trong `spa_staff_payroll`.
- Open risks: DB chưa upgrade `spa_staff_payroll` sẽ chưa thấy setting/màu; composite tree line chưa hiện flag (chỉ form line) — constraint vẫn enforce.
- Next suggested steps: upgrade `-u spa_staff_payroll` rồi kiểm UI lịch.

### 2026-07-14 - Calendar title: hiển thị mã KH trước tên KH
- Goal: trên ô lịch đặt lịch, hiện thêm `customer_code` ngay trước tên khách hàng.
- Changes made:
  - `_compute_calendar_event_title`: ghép `partner_id.customer_code` trước tên (`CODE Name (phone)`); field đã có trong `@api.depends` từ trước nhưng chưa dùng.
  - Cập nhật assertion test tiêu đề lịch.
- Files touched:
  - `models/spa_service_booking.py`
  - `tests/test_booking_calendar.py`
  - `docs/WORKLOG.md`, `docs/AGENT_REFERENCE.md`
- Validation done:
  - targeted test `test_calendar_event_title_one_line_with_nickname_phone_service` (xem lệnh trong mục Validation của phản hồi task).
- Dependency impact check:
  - Dependents reviewed: calendar `create_name_field="calendar_event_title"`; popover dùng `partner_id` (name_get) riêng, không phụ thuộc title; reminder activity summary không đổi; JS color patches không đọc format title.
  - Contract compatibility result: không đổi tên field/XML id; chỉ đổi chuỗi compute `calendar_event_title`.
  - Regression tests/manual checks run: test title ở trên; manual: reload lịch → ô event có mã KH trước tên.
- Open risks: KH thiếu `customer_code` vẫn hiện tên như cũ.
- Next suggested steps: none.

### 2026-06-20 - Nhắc lịch KH qua Zalo ZNS (module mới spa_zalo_oa)
- Goal: gửi tin tự động cho khách hàng qua Zalo; làm trước tính năng nhắc lịch hẹn (cấu hình trước N giờ/ngày).
- Changes made:
  - Tạo module mới `custom_addons/spa_zalo_oa` (depends `booking_calendar`) gửi ZNS qua Zalo OA: model token OA (`spa.zalo.oa.account`) + helper `zalo_oapi` + hàng đợi/nhật ký tin (`spa.zalo.message`) + cron refresh token / enqueue reminder / gửi hàng đợi.
  - Inherit `spa.service.booking`: thêm field `zalo_reminder_sent` (cờ RIÊNG, không đụng `reminder_sent` của nhắc nhân viên) + `_cron_send_zalo_reminders()` enqueue tin nhắc cho lịch sắp tới.
- Files touched:
  - Mới: toàn bộ `custom_addons/spa_zalo_oa/**`.
  - Không sửa file gốc của `booking_calendar` (chỉ `_inherit` từ module mới).
- Validation done:
  - `py_compile` toàn bộ python + validate XML well-formed (pass).
  - Tests module-local `spa_zalo_oa/tests/test_zalo_reminder.py` (mock network) — xem lệnh chạy trong WORKLOG spa.
- Dependency impact check:
  - Dependents reviewed: `spa.service.booking` (thêm field/cron qua inherit), cron `_cron_send_booking_reminders` (nhắc NV) KHÔNG đổi; calendar/list views không phụ thuộc field mới.
  - Contract compatibility result: không đổi field/model/XML id hiện có; chỉ thêm field `zalo_reminder_sent` (additive, index).
  - Regression tests/manual checks run: tests mới (enqueue/optout/queue/refresh/cron window). Manual: bật setting + nhập OA + template → tạo booking trong window → chạy cron → tin vào hàng đợi → gửi.
- Open risks: ZNS cần OA thật + template duyệt + đúng tên tham số template (`name/date/time/service`); token phải được refresh (cron 12h). Phí/tin theo Zalo.
- Next suggested steps: bổ sung sự kiện booking_confirm, birthday, session_done, promo theo cùng hàng đợi.

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

