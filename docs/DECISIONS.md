# Decisions (ADR)

> Đọc khi sắp đổi kiến trúc. Chi tiết đầy đủ: `archive/DECISIONS_FULL.md`

| ID | Decision | Files |
|----|----------|-------|
| DEC-01 | Billing centralized in `rental_contract_services` | `services/rental_contract_services.py` |
| DEC-02 | Primary invoice = `account.move` (not `rental.invoice`) | `models/account_move.py`, `wizard/create_invoice_wizard.py` |
| DEC-03 | Contract edit lock via `write()` + context bypass | `models/rental_contract.py` |
| DEC-04 | Transport done via picking + `sudo` | `models/stock_picking.py`, `models/transport.py` |
| DEC-05 | Courier isolated from staff (record rules) | `security/ir_rule.xml`, `views/menu.xml` |
| DEC-06 | Matrix model + non-overlap constraint | `models/rental_transport_matrix.py` |
| DEC-07 | Multi-company via `mc.group.mixin` | `models/models.py`, `security/ir_rule.xml` |
| DEC-08 | Excel import transport (col C=plate, neg qty=return) | `helper/import_transport_matrix.py`, `wizard/rental_transport_import_wizard.py` |

**New ADR:** thêm 1 dòng vào bảng + ghi đầy đủ vào `archive/DECISIONS_FULL.md` nếu cần.
