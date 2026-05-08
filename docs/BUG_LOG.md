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

