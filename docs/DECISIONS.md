# Rental Decisions (ADR Lite)

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

### [RENTAL-DEC-2026-06-04-01] Billing logic centralized in `rental_contract_services`

- Date: 2026-06-04
- Status: accepted (existing)
- Context: Cùng một kỳ thuê phải ra cùng số trên bảng Excel, `rental.invoice` (legacy) và `account.move`.
- Decision: Mọi tính ngày thuê, trừ holiday, đơn giá ngày/tháng, gộp dòng theo template → `services/rental_contract_services.py`; model/controller chỉ orchestration.
- Consequences: Sửa giá hoặc công thức: một file service + test `test_rental_holiday_days`; tránh copy logic sang controller.
- Alternatives considered: Compute thuần trên `rental.contract` hoặc SQL view.
- Related files/modules: `services/rental_contract_services.py`, `models/rental_contract.py`, `models/account_move.py`, `controllers/rental_contract_controller.py`

### [RENTAL-DEC-2026-06-04-02] Primary invoicing via Odoo `account.move`, not `rental.invoice`

- Date: 2026-06-04
- Status: accepted (existing)
- Context: Cần hóa đơn kế toán chuẩn, công nợ, báo cáo.
- Decision: Luồng chính `action_create_rental_invoice` → `account.move` + `business_xlsx_attachment_id`; `rental.invoice` giữ cho `action_create_invoice` / báo cáo cũ.
- Consequences: Menu "Rental invoice" trỏ action account; module phụ thuộc runtime `account` dù manifest chưa liệt kê.
- Alternatives considered: Chỉ dùng model `rental.invoice` nội bộ.
- Related files/modules: `models/rental_contract.py`, `models/account_move.py`, `views/menu.xml`, `wizard/create_invoice_wizard.py`

### [RENTAL-DEC-2026-06-04-03] Contract edit lock with field-level `write` guard

- Date: 2026-06-04
- Status: accepted (existing)
- Context: Sau khi gửi duyệt, không cho sửa tab thông tin cơ bản; vẫn cho phép cập nhật từ stock/picking.
- Decision: `can_edit` + `blocked_fields` trong `rental.contract.write`; workflow/status dùng `rental_contract_allow_locked_write`; Leader mở `edit_unlocked`.
- Consequences: Mọi write từ code khác vào blocked fields khi khóa sẽ lỗi — dùng context hoặc tránh ghi các field đó.
- Alternatives considered: `ir.rule` read-only; state machine trên từng field.
- Related files/modules: `models/rental_contract.py`, `views/rental_contract_view.xml`

### [RENTAL-DEC-2026-06-04-04] Transport completion via stock picking + `sudo`

- Date: 2026-06-04
- Status: accepted (existing)
- Context: Nhóm courier có quyền validate picking nhưng không write `rr.transport`.
- Decision: `stock.picking._action_done` → `_rental_sync_transport_done_from_picking` → `transport.sudo().write({'state': 'done'})`.
- Consequences: Phải giữ picking gắn `rental_transport_id`; return picking bị bỏ qua (`return_id`).
- Alternatives considered: Grant write ACL courier trên transport; computed state từ picking.
- Related files/modules: `models/stock_picking.py`, `models/transport.py`, `security/ir_rule.xml`

### [RENTAL-DEC-2026-06-04-05] Courier role isolated from Rental Staff

- Date: 2026-06-04
- Status: accepted (existing)
- Context: Người giao/nhận chỉ cần kho, không xem toàn bộ HĐ/transport list.
- Decision: `group_rental_transport_courier` không implied staff; record rules lọc transport/picking theo `user.partner_id`; menu Stock hạn chế.
- Consequences: Không gán đồng thời staff + courier trên cùng user nếu muốn tách quyền rõ; field `rental_contract_id` trên transport có `groups=staff`.
- Alternatives considered: Staff readonly song song SPA.
- Related files/modules: `security/custom_security_groups.xml`, `security/ir_rule.xml`, `views/menu.xml`, `models/transport.py`

### [RENTAL-DEC-2026-06-04-06] `rental.transport.matrix` persisted with non-overlap constraint

- Date: 2026-06-04
- Status: accepted (existing)
- Context: Bảng xác nhận khối lượng theo kỳ phải lưu lại và không trùng kỳ trên một HĐ.
- Decision: Model riêng + SQL-level overlap check + wizard khi tạo từ HĐ trùng kỳ; HTML matrix compute từ transports.
- Consequences: Test `test_rental_transport_matrix_overlap`; xóa HĐ cascade matrix.
- Alternatives considered: Chỉ JSON trên HĐ (`rr_transport_matrix_json` đã comment HTML cũ).
- Related files/modules: `models/rental_transport_matrix.py`, `wizard/rental_transport_matrix_overlap_wizard.py`, `tests/test_rental_transport_matrix_overlap.py`

### [RENTAL-DEC-2026-06-04-07] Multi-company via in-module `mc.group.mixin`

- Date: 2026-06-04
- Status: accepted (existing)
- Context: Nhiều chi nhánh, dữ liệu tách theo `res.company`.
- Decision: Mixin nội bộ module (không module riêng); `company_group_id` related từ `company_id.company_group_id`; `ir.rule` domain `company_id in company_ids`.
- Consequences: Model mới cần inherit mixin + rule tương ứng.
- Alternatives considered: Module `multi_company` OCA riêng.
- Related files/modules: `models/models.py`, `security/ir_rule.xml`
