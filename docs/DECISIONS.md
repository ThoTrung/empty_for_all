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

### [BC-DEC-2026-05-08-05] Calendar behavior extension through guarded JS patches
- Date: 2026-05-08
- Status: accepted (existing)
- Context: core calendar behavior needed domain-specific interaction and styling.
- Decision: patch renderer/controller/model in backend assets, guarded by `resModel == spa.service.booking`.
- Consequences: high flexibility, but upgrade fragility when Odoo web internals change.
- Alternatives considered: only XML-level customization with limited behavior control.
- Related files/modules: `static/src/js/spa_booking_calendar_view.js`, `static/src/js/spa_booking_calendar_renderer.js`

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

