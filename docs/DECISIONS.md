# Booking Calendar Decisions (ADR Lite)

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

### [BC-DEC-2026-08-19-01] Tree list: default_order desc + Mã KH/sdt
- Date: 2026-08-19
- Status: accepted
- Context: List Đặt lịch / Lịch phục vụ cần lịch mới lên đầu; ẩn mã đặt lịch và giờ kết thúc; hiện Mã KH trước tên KH và sdt sau tên.
- Decision: `default_order="start_datetime desc, id desc"` trên tree chung (không đổi `_order` model). Related readonly `partner_customer_code` / `partner_phone`. `name` và `end_datetime` `optional="hide"`.
- Consequences: operator tree (primary inherit) nhận cùng arch. Browser có thể nhớ cột optional cũ cho đến khi user reset.
- Alternatives considered: đổi `_order` model (rejected — ảnh hưởng search/RPC khác); chỉ xpath operator tree (rejected — cùng bộ cột trên Đặt lịch).
- Related files/modules: `models/spa_service_booking.py`, `views/spa_service_booking_view.xml`, `tests/test_booking_calendar.py`

### [BC-DEC-2026-07-26-02] Lịch phục vụ cho Spa Booking Operator
- Date: 2026-07-26
- Status: accepted (amended 2026-08-19)
- Context: Cần màn nhân viên nhận việc: chỉ confirmed/doing/done; Phục vụ/Hoàn thành; bắt buộc có Nhân viên thực hiện (`staff_ids` hoặc line `staff_id`); không CRUD lịch; máy chung một login. 2026-08-19: operator cần gán/đổi NV trên form chi tiết.
- Decision: record rule gate theo state khi có `group_spa_booking_operator` và không có `group_spa_staff`; ACL read+write booking/line (write whitelist `staff_ids` / line `staff_id`); `action_doing`/`action_done` dùng sudo+`spa_booking_operator_transition` cho operator-only; chặn create/unlink/confirm/cancel/draft; menu/action **Lịch phục vụ**; form operator `edit=1` với field khác readonly; calendar `display_start_datetime` readonly (không kéo giờ); popover chỉ Phục vụ/Hoàn thành cho operator.
- Consequences: `action_doing` bắt buộc NV thực hiện với **mọi** user; legacy `staff_id` alone không đủ. Operator đổi NV trên confirmed/doing; không đổi khi done/cancel/`is_locked`.
- Alternatives considered: acting-staff session (rejected); lọc done theo env.user (rejected trên máy chung); mở CRUD form (rejected — whitelist field).
- Related files/modules: `security/staff_booking_operator_security.xml`, `models/spa_service_booking.py`, `spa_service_booking_line.py`, views/menu, popover JS/XML, `spa_staff_payroll` operator form inherit, `tests/test_booking_operator.py`.

### [BC-DEC-2026-07-26-01] Calendar menus split by booking_board selection
- Date: 2026-07-26
- Status: accepted
- Context: Trước đây menu Đặt lịch (Bác sĩ) / (Chuyên viên) lọc theo computed `is_doctor_route` (product yêu cầu doctor hoặc có NV doctor). User muốn không phụ thuộc cấp độ NV nữa.
- Decision: Thêm Selection `booking_board` (`specialist` / `doctor`, default `specialist`). Action Doctor/Specialist domain theo `booking_board`; context `default_booking_board` theo menu. Giữ `spa_allowed_staff_levels` khi chọn thẻ/NV. Migrate dữ liệu cũ từ `is_doctor_route`. Xóa field compute `is_doctor_route`.
- Consequences: Đổi NV/dịch vụ không chuyển bảng lịch; `booking_board` ẩn trên form/tree/search (chỉ gán từ menu context / copy parent). Recurring/child copy `booking_board` từ parent.
- Alternatives considered: Giữ compute theo cấp độ; chỉ thêm field song song với `is_doctor_route`.
- Related files/modules: `models/spa_service_booking.py`, `views/spa_service_booking_view.xml`, `migrations/17.0.1.1.0/pre-migrate.py`

### [BC-DEC-2026-07-14-02] Customer-requested calendar color lives in spa_staff_payroll
- Date: 2026-07-14
- Status: accepted
- Context: Flag `spa_payroll_customer_requested` thuộc payroll; cần tô cam lịch ở draft/confirmed, cấu hình được, và bắt buộc có NV khi tick.
- Decision: implement override color compute + settings ICP + staff constrains trong `spa_staff_payroll` (không thêm depends ngược vào `booking_calendar`). Customer-requested thắng mọi draft-special khi draft; confirmed dùng state HEX override; doing/done/cancel không đổi. Booking gộp: bất kỳ line tick cũng áp màu parent.
- Consequences: màu lịch phụ thuộc module payroll khi module được cài; JS calendar không cần đổi nếu compute `state_*` / `draft_special_*` đủ.
- Alternatives considered: đưa field/color vào `booking_calendar` (tạo coupling payroll vào core calendar).
- Related files/modules: `spa_staff_payroll/models/spa_booking_payroll_fields.py`, `spa_staff_payroll/models/res_config_settings.py`

### [BC-DEC-2026-07-14-01] Calendar title shows customer_code before customer name
- Date: 2026-07-14
- Status: accepted
- Context: staff cần nhận diện nhanh KH trên ô lịch; `customer_code` đã có trong `@api.depends` nhưng chưa được ghép vào title.
- Decision: format khách trên `calendar_event_title` là `CODE Name (phone)` (bỏ mã nếu trống).
- Consequences: ô lịch dài hơn một chút khi mã dài; không đổi popover (`partner_id` vẫn dùng `name_get`).
- Alternatives considered: chỉ hiện mã (thiếu tên), hoặc `name_get` đầy đủ phone/code/name/sub_phones (quá dài cho ô calendar).
- Related files/modules: `models/spa_service_booking.py`, `tests/test_booking_calendar.py`

### [BC-DEC-2026-05-08-05] Calendar behavior extension through guarded JS patches
- Date: 2026-05-08
- Status: accepted (existing)
- Context: core calendar behavior needed domain-specific interaction and styling.
- Decision: patch renderer/controller/model in backend assets, guarded by `resModel == spa.service.booking`.
- Consequences: high flexibility, but upgrade fragility when Odoo web internals change.
- Alternatives considered: only XML-level customization with limited behavior control.
- Related files/modules: `static/src/js/spa_booking_calendar_view.js`, `static/src/js/spa_booking_calendar_renderer.js`

### [BC-DEC-2026-08-22-01] Shift gate only when day roster is published (Phase 1)
- Date: 2026-08-22
- Status: accepted
- Context: Hard shift check blocked OT and future bookings when `booking.shift.config` missing for the day. Industry practice (Mindbody off-day booking) allows front-desk override when roster exists but slot is outside window.
- Decision: If no `booking.shift.config` with lines for the booking's local day(s), skip shift constraint (still enforce level + capacity). When day roster is published, slot must fit shift window unless `staff_outside_shift` is set on booking (or line for composite). Suggestions still prefer in-shift staff when roster applies.
- Consequences: amends operational effect of BC-DEC-2026-05-08-04 (day config is SoT **when published**, not “missing config = nobody assignable”). Phase 2 week template materialize remains separate.
- Alternatives considered: virtual week template resolve (rejected — dual SoT); manager-only flag (rejected — blocks front desk OT).
- Related files/modules: `models/booking_shift_config.py`, `models/spa_service_booking.py`, `models/spa_service_booking_line.py`, `tests/test_booking_calendar.py`

### [BC-DEC-2026-08-22-02] Week shift template materialize-only (Phase 2a)
- Date: 2026-08-22
- Status: accepted
- Context: Phase 1 leaves future days “open” without roster; operators need Mindbody-style weekly pattern → daily `booking.shift.config` records without virtual resolve.
- Decision: `booking.shift.week.template` (weekday lines) + apply wizard with date range. Default **skip** days that already have shift lines; optional `overwrite_existing`. One SoT remains `booking.shift.config`.
- Consequences: no dual SoT; manual holiday edits preserved unless overwrite ticked. Default apply range in wizard UI: ~4 weeks from today.
- Alternatives considered: merge union policy (deferred); virtual template resolve (rejected).
- Related files/modules: `models/booking_shift_week_template.py`, `views/booking_shift_week_template_views.xml`

### [BC-DEC-2026-08-22-03] Recurring staff copy with per-child validation (Phase 2b)
- Date: 2026-08-22
- Status: accepted
- Context: Recurring children previously had no staff; copying staff blindly risks shift/capacity violations across dates.
- Decision: Optional `recurring_copy_staff` on parent. Each child created with staff + outside-shift flags when needed; on ValidationError, retry child without staff and post chatter listing skipped dates.
- Consequences: no mass auto-tick outside-shift; some children may lack staff until operator assigns.
- Alternatives considered: always copy staff (rejected); block entire recurring on first failure (rejected).
- Related files/modules: `models/spa_service_booking.py` (`action_confirm_recurring`, `_create_recurring_child_booking`)

### [BC-DEC-2026-05-08-04] Day-based shift config as staff availability source of truth
- Date: 2026-05-08
- Status: accepted (existing)
- Context: scheduling needs dynamic daily shift assignment.
- Decision: use `booking.shift.config` + lines per date instead of fixed staff shift fields only.
- Consequences: flexible daily planning with extra admin setup responsibility.
- Alternatives considered: rely solely on static user shift fields.
- Related files/modules: `models/booking_shift_config.py`, `models/spa_service_booking.py`

### [BC-DEC-2026-05-08-03] Parent-only calendar visibility for booking chains
- Date: 2026-05-08
- Status: accepted (existing)
- Context: recurring/chain bookings can clutter calendar and reduce readability.
- Decision: expose only parent-level booking blocks (`display_is_calendar_parent`) in key calendar/list actions.
- Consequences: cleaner calendar; child navigation handled via chain actions/forms.
- Alternatives considered: display all child bookings directly in calendar.
- Related files/modules: `models/spa_service_booking.py`, `views/spa_service_booking_view.xml`

### [BC-DEC-2026-05-08-02] Completion is delegated by booking kind
- Date: 2026-05-08
- Status: accepted (existing)
- Context: booking can represent treatment-card or non-session offerings.
- Decision: resolve completion target through model pointer fields and call target `spa_complete_booking`.
- Consequences: extensible completion path with more pointer consistency checks required.
- Alternatives considered: hardcode completion logic in booking model only.
- Related files/modules: `models/spa_service_booking.py`, `models/spa_booking_non_session_offering.py`, `models/spa_treatment_session_booking.py`

### [BC-DEC-2026-05-08-01] Draft bookings consume staff capacity in conflict checks
- Date: 2026-05-08
- Status: accepted (existing)
- Context: practical scheduling needs reservation-like behavior before confirmation.
- Decision: include draft bookings in capacity calculations to prevent overbooking.
- Consequences: safer capacity planning; requires explicit handling for stale drafts.
- Alternatives considered: only confirmed/doing bookings count toward capacity.
- Related files/modules: `models/spa_service_booking.py`, `tests/test_booking_calendar.py`

