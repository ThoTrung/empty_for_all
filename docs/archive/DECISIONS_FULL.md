# Decisions — full archive

### DEC-01 — Billing in `rental_contract_services`
- Context: Same period must match Excel, rental.invoice, account.move
- Decision: All day/holiday/price logic in services; models orchestrate only
- Files: `services/rental_contract_services.py`, `models/rental_contract.py`, `models/account_move.py`

### DEC-02 — Primary invoicing via `account.move`
- Context: Standard accounting, receivables
- Decision: `action_create_rental_invoice` → account.move + XLSX attachment; rental.invoice legacy
- Files: `models/rental_contract.py`, `models/account_move.py`, `wizard/create_invoice_wizard.py`

### DEC-03 — Contract edit lock
- Context: Block base tab edits after submit; allow stock updates
- Decision: `can_edit` + blocked_fields in write(); context bypass for workflow
- Files: `models/rental_contract.py`, `views/rental_contract_view.xml`

### DEC-04 — Transport done via picking
- Context: Courier can validate picking but not write transport
- Decision: stock.picking._action_done → sudo write transport state done
- Files: `models/stock_picking.py`, `models/transport.py`

### DEC-05 — Courier isolated
- Context: Couriers only need warehouse access
- Decision: Separate group, record rules on partner_id, limited menus
- Files: `security/custom_security_groups.xml`, `security/ir_rule.xml`

### DEC-06 — Matrix non-overlap
- Context: Volume confirmation per period
- Decision: Separate model + SQL overlap + wizard
- Files: `models/rental_transport_matrix.py`, overlap wizard, tests

### DEC-07 — mc.group.mixin
- Context: Multi-branch companies
- Decision: In-module mixin + company_id rules
- Files: `models/models.py`, `security/ir_rule.xml`

### DEC-05-01 — Excel import transport
- Context: Import from volume matrix Excel
- Decision: Wizard on contract tab; parser in helper; col C plate; neg qty return; dup in file errors; allow re-import on contract
- Files: `helper/import_transport_matrix.py`, import wizard, tests
