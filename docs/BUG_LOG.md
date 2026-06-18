# Bug log

> Active bugs + tech debt. Resolved history: `archive/BUG_LOG_RESOLVED.md`

## Active

_(none)_

## Tech debt

| ID | Risk | Direction |
|----|------|-----------|
| DEBT-01 | Manifest missing `account`,`mail` | Add to `depends` after prod check |
| DEBT-02 | `rental.invoice.line` compute uses `write()` | Assign fields in compute |
| DEBT-03 | Controllers `sudo()` without company check | Validate `company_id in env.companies` |

**New bug:** 1 dòng vào Active hoặc Tech debt; resolved → move to archive.
