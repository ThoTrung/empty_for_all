# Rental Worklog

Chronological notes for agents and developers. Newest entries at the top.

## Template

### YYYY-MM-DD — Short title

- Author/agent:
- Task:
- Files touched:
- Validation:
- Notes / follow-up:

---

## 2026-06-04 — Initial agent memory docs

- Author/agent: Cursor agent
- Task: Phân tích module `rental` và tạo bộ memory docs (`AGENT_REFERENCE`, `DECISIONS`, `BUG_LOG`, `WORKLOG`).
- Files touched:
  - `docs/AGENT_REFERENCE.md` (new)
  - `docs/DECISIONS.md` (new)
  - `docs/BUG_LOG.md` (new)
  - `docs/WORKLOG.md` (new)
- Validation: Đọc toàn bộ cây Python/XML chính; đối chiếu manifest, security, services, tests; chưa chạy `odoo-bin --test-enable`.
- Notes / follow-up:
  - Cân nhắc thêm `account`, `mail` vào `depends`.
  - Có thể thêm `docs/AGENT_SESSION_DEFAULTS.md` ở repo root nếu đồng bộ với `spa`/`booking_calendar`.
