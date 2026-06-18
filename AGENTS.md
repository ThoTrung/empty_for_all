# Rental — agent entry (đọc duy nhất file này trước)

Odoo 17 · `custom_addons/odoo_modules/rental` · depends: `base,web,stock,sale,sale_management` (+ runtime: `account`, `mail`)

## Rules

| # | Rule |
|---|------|
| 1 | Billing → `services/rental_contract_services.py` only |
| 2 | Contract lock → test `write()` + `rental_contract_allow_locked_write` |
| 3 | New model → ACL + `ir.rule` (+ courier rule if picking) |
| 4 | Controllers `sudo()` → check `company_id` after browse |
| 5 | Schema change → `__manifest__.py` version + `migrations/` |

## Task → file

| Task | Where |
|------|-------|
| Contract / workflow | `models/rental_contract.py`, `views/rental_contract_view.xml` |
| Transport | `models/transport.py`, `models/stock_picking.py` |
| Excel import | `helper/import_transport_matrix.py`, `wizard/rental_transport_import_wizard.py` |
| Matrix | `models/rental_transport_matrix.py` |
| Invoice / payment XLSX | `models/account_move.py`, `wizard/create_invoice_wizard.py`, `controllers/rental_contract_controller.py` |
| Print DOCX/PDF/XLSX | `models/rental_template.py`, `helper/export_excel_template.py` |
| Security | `security/custom_security_groups.xml`, `ir_rule.xml`, `ir_model_access.xml` |

## Docs (chỉ mở khi cần)

| Khi | File |
|-----|------|
| Model/security/workflow chi tiết | `docs/AGENT_REFERENCE.md` |
| Quyết định kiến trúc | `docs/DECISIONS.md` |
| Bug / tech debt | `docs/BUG_LOG.md` |
| Lịch sử phiên gần đây | `docs/WORKLOG.md` (3 entry đầu) |

## Dev

```bash
odoo-bin -c conf/odoo.conf -d rental -u rental --test-enable --stop-after-init
```
