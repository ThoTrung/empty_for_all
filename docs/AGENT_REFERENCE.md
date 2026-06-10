# Rental Module Reference (Living Doc)

> **Phiên làm việc:** Đọc file này trước, sau đó `BUG_LOG.md`, `DECISIONS.md`, `WORKLOG.md`. Module nằm tại `custom_addons/odoo_modules/rental` (addons path: `/mnt/extra-addons/odoo_modules`).

## 1) Business Scope

- **Mục đích:** Quản lý cho thuê thiết bị/xây dựng (hợp đồng hai bên A/B, gói thầu, xuất nhập kho theo chuyến xe, bảng xác nhận khối lượng, hóa đơn thuê, in/xuất DOCX–PDF–XLSX).
- **Vai trò chính:**
  - **Rental Staff** — hợp đồng, sản phẩm, vận chuyển, hóa đơn nội bộ.
  - **Rental Leader** — duyệt hợp đồng, mở khóa chỉnh sửa.
  - **Rental Manager / Admin** — cấu hình đầy đủ.
  - **Người giao/nhận hàng** (`group_rental_transport_courier`) — menu kho hạn chế, chỉ phiếu `rr.transport` / `stock.picking` được gán.
- **Kết quả mong đợi:** Chu trình HĐ (draft → duyệt → hiệu lực), tính tiền thuê nhất quán (ngày/tháng + ngày nghỉ), ma trận khối lượng không trùng kỳ, hóa đơn `account.move` kèm bảng thanh toán Excel.

## 2) Technical Scope

### Models (module-owned)

| Model | Mô tả ngắn |
|-------|------------|
| `rental.contract` | Hợp đồng thuê (trung tâm nghiệp vụ) |
| `rental.contract.line` | Dòng báo giá trên HĐ |
| `rr.transport` / `rr.transport.line` | Phiếu xuất/nhập kho (giao/trả) |
| `rental.transport.matrix` | Bảng xác nhận khối lượng (HTML + Excel) |
| `rental.invoice` / `rental.invoice.line` | Hóa đơn thuê nội bộ (legacy; luồng chính dùng `account.move`) |
| `construction.project` / `construction.address` / `construction.work` | Dự án / địa chỉ / gói thầu |
| `transport.truck` | Xe vận chuyển |
| `rental.template` | Mẫu file DOCX/XLSX theo công ty |
| `rental.product.template.set` (+ line) | Bộ mẫu SP nạp vào HĐ |
| `rental.holiday` | Kỳ nghỉ (trừ ngày khi tính tiền thuê) |
| `mc.group.mixin` | `company_id` + `company_group_id` (multi-company) |
| `amount_to_text.vi` | Số tiền → chữ tiếng Việt |

### Models (inherit)

- `res.partner` — `customer_type`: renter / driver / my_company_profile / other
- `res.users` — `rental_leader_id`, `is_rental_leader`
- `res.company` — mở rộng nhẹ (xem `res_company.py`)
- `product.template` / `product.product` / `product.template.attribute.value` — giá thuê, multiplier biến thể, ĐVT hiển thị NV
- `sale.order.line` — mở rộng nhẹ
- `stock.picking` — `rental_transport_id`, đồng bộ `rr.transport.state` khi done
- `account.move` / `account.move.line` — `rental_contract_id`, kỳ thuê, `business_xlsx_attachment_id`

### Wizards

- `create.invoice.wizard` — chọn kỳ, gọi callback trên HĐ (xuất Excel / tạo hóa đơn)
- `rental.reject.confirm.wizard` — Leader từ chối → `need_fix`
- `rental.transport.matrix.overlap.wizard` — xử lý khi tạo matrix trùng kỳ
- `rental.transport.import.wizard` — import `rr.transport` từ Excel ma trận khối lượng (tab Transports trên HĐ)
- `rental.link_child_contact.wizard` — gắn đại diện con vào công ty renter

### Services (`services/rental_contract_services.py`)

Logic **tính tiền thuê** dùng chung cho Excel, `rental.invoice`, `account.move`:

- `rental_days_between_with_holiday` — trừ `rental.holiday`
- `unit_price_for_transport_line` — `day` vs `month` (`rental_billing_mode`)
- `calc_rental_contract_invoice` / `calc_rental_payment_table_grouped_by_template`
- `render_rental_contract_docx` — in hợp đồng DOCX

### Controllers

- `rental_contract_controller.py` — tải báo giá XLSX, in HĐ PDF, ma trận Excel, v.v. (`auth='user'`, nhiều chỗ `sudo()`)
- `rental_transport_controller.py` — in phiếu vận chuyển

### Frontend assets

- `static/src/js/big_modal_dialog.js`, `download_and_close.js`
- `static/src/scss/style.scss`, `rental_modal.scss`

## 3) Data Model Notes

### Hợp đồng (`rental.contract`)

- **Hai bên:** A = renter (`customer_type=renter`, công ty), B = công ty Odoo hiện tại (branch con của `company_partner_id`).
- **Trạng thái:** `new` → `need_approve` → `leader_approved` → `customer_confirmed` → `active` → `finish` (có `break`, `need_fix`).
- **Khóa sửa:** `can_edit` = `new`/`need_fix` hoặc `edit_unlocked` (Leader). `write()` chặn một tập field khi khóa; workflow dùng context `rental_contract_allow_locked_write=True`.
- **Tính tiền:** `rental_billing_mode` (`day`|`month`), `include_start_day_bob` / `include_start_day_current` (có tính ngày bắt đầu kỳ hay không).
- **Liên kết:** `rr_transport_ids`, `rental_invoice_ids`, `account_move_ids`, `transport_matrix_ids`.

### Vận chuyển (`rr.transport`)

- Loại `delivery` / `return`; dòng `rr.transport.line` gắn `product_id`, `qty`, ngày.
- Tạo `stock.picking`; khi picking done (không phải return) → `transport.state = done` qua `sudo()`.
- Nhóm **courier** không có `perm_write` trên transport — chỉ thao tác picking.

### Sản phẩm

- `rental_price_day` trên template → đồng bộ variant theo tỷ lệ `lst_price/list_price`.
- `price_multiplier` trên PTAV → `price_extra` và giá biến thể.
- `staff_display_uom_id` — chỉ hiển thị; kho vẫn `uom_id` mẫu.

### Ma trận khối lượng

- Model `rental.transport.matrix`: constraint không overlap kỳ trên cùng HĐ.
- Sort cột theo chiều dài parse từ nhãn (vd. `2m`, `1,5m`).

## 4) View Architecture

- Menu gốc `menu_rental_root` — Contract, Stock, Renters, Drivers, Settings (templates, holidays, …).
- HĐ: form lớn với tab Base / Transport / Invoice / … (`rental_contract_view.xml`).
- `res.partner` — form tùy biến theo `customer_type`; quick form tạo HĐ từ renter.
- Action **My company profile** — form một bản ghi (`my_company_profile`), `res_id` động qua Python.
- Courier: menu Stock chỉ product (read) + xuất nhập kho.

## 5) Security Model

### Groups (`security/custom_security_groups.xml`)

1. `group_rental_staff`
2. `group_rental_leader` (implied staff)
3. `group_rental_manager` (implied leader)
4. `group_rental_admin` (implied manager; gán root/admin)
5. `group_rental_transport_courier` — **không** implied staff; có `stock.group_stock_user`

### Record rules (`security/ir_rule.xml`)

- Multi-company: `company_id in company_ids` trên HĐ, transport, matrix, invoice, construction, truck, …
- Courier: chỉ `rr.transport` / lines / pickings khi `deliverer_partner_id` hoặc `receiver_partner_id` = `user.partner_id`.

### ACL

- `security/ir_model_access.xml` — phân quyền theo nhóm trên toàn bộ model module.

### Rủi ro

- Controllers và `stock_picking` dùng `sudo()` — mở rộng phải kiểm tra `auth` + group.
- `rr.transport.rental_contract_id` có `groups='rental.group_rental_staff'` — courier không đọc field qua ORM thường (dùng related/summary).

## 6) Main Workflows

### Duyệt hợp đồng

```
new/need_fix --[request_confirm]--> need_approve --[leader_confirm]--> leader_approved
     ^                                      |
     +--[reject wizard]-- need_fix          +--[customer_confirm]--> customer_confirmed
                                                      |
                                              [active] --> active --> [finish] --> finish
                                                                    <-- [reactivate] --
```

- Tạo HĐ: subscribe `staff_id.rental_leader_id` vào chatter.
- Leader: `action_unlock_edit` / `action_lock_edit`.

### Xuất nhập kho → tính tiền

1. Nhập `rr.transport` + lines trên HĐ (thủ công hoặc **Import từ Excel** trên tab Transports).
2. Xác nhận picking → transport `done`.
3. Wizard kỳ → `action_export_invoice_excel` hoặc `action_create_rental_invoice`:
   - Gộp theo transport lines + ngày nghỉ + mode day/month.
   - Tạo `account.move` + đính kèm XLSX bảng thanh toán.

### Bảng xác nhận khối lượng

- `action_create_transport_matrix_record` → `rental.transport.matrix` (overlap → wizard).
- Export Excel qua controller / action trên matrix.

### In tài liệu

- HĐ: DOCX template (`rental.template` hoặc `static/file_template/`) → PDF (LibreOffice / `docx2pdf`).
- Yêu cầu server: `libreoffice` (Ubuntu) hoặc `pip install docx2pdf` (xem `Readme.md`).

## 7) Dependencies

### Khai báo (`__manifest__.py`)

`base`, `web`, `stock`, `sale`, `sale_management`

### Phụ thuộc thực tế (chưa khai báo — cần cẩn thận)

| Module | Dùng ở đâu |
|--------|------------|
| `account` | `account.move`, journal, taxes, menu hóa đơn |
| `mail` | `mail.thread`, `message_post`, `message_subscribe` trên HĐ/transport |

Trước khi deploy DB mới: đảm bảo `account` (và thực tế `mail`) đã cài. Cân nhắc bổ sung vào `depends` khi refactor.

### Python bên ngoài Odoo

- `openpyxl`, `docxtpl`, tùy môi trường `docx2pdf`
- LibreOffice CLI cho PDF

## 8) Tests

- `tests/test_rental_holiday_days.py` — `rental_days_between_with_holiday`
- `tests/test_rental_transport_matrix_overlap.py` — constraint overlap matrix
- Chạy:

```bash
odoo-bin -d <db> -u rental --test-enable --stop-after-init
```

### Khoảng trống coverage

- Workflow duyệt HĐ, khóa `write`
- `action_create_rental_invoice` / `account.move`
- Controllers PDF/XLSX + quyền courier
- Đồng bộ picking → transport

## 9) Known Pitfalls

| Vấn đề | Triệu chứng | Gợi ý xử lý |
|--------|-------------|-------------|
| Thiếu `account` trong depends | Cài module trên DB chỉ có sale/stock | Thêm `account` vào manifest hoặc cài thủ công trước |
| `mail` không trong depends | Lỗi khi `message_post` nếu mail chưa cài | Cài `mail` hoặc khai báo depends |
| `_compute_total_price` dùng `rec.write()` trong compute (`rental.invoice.line`) | Recompute loop / chậm | Refactor sang gán trực tiếp field |
| Controller `sudo().browse(contract_id)` | User có thể tải HĐ công ty khác nếu biết ID | Kiểm tra `company_id` / record rules sau browse |
| Courier + transport field `groups=staff` | UI/API thiếu contract trên transport | Dùng `rental_contract_summary` / picking |
| Hard-coded template paths | Công ty chưa upload `rental.template` | Fallback `static/file_template/*.xlsx/docx` |

## 10) Change Protocol For New Agents

1. Đọc `docs/AGENT_REFERENCE.md` → `BUG_LOG.md` → `DECISIONS.md` → `WORKLOG.md`.
2. Xác nhận `depends` và DB đã có `account` (+ `mail`) trước khi chạm hóa đơn/chatter.
3. Logic tính tiền: **ưu tiên sửa trong** `rental_contract_services.py`, không nhân đôi trên model/controller.
4. Thay đổi khóa HĐ / status: test cả `write()` blocked fields và context `rental_contract_allow_locked_write`.
5. Thêm model: ACL + `ir.rule` multi-company (+ courier nếu liên quan picking).
6. Sau thay đổi phiên bản: cập nhật `__manifest__.py` version + migration `migrations/<version>/` nếu đổi schema.
7. Ghi validation vào `WORKLOG.md`; quyết định kiến trúc vào `DECISIONS.md`; bug vào `BUG_LOG.md`.

### Lệnh phát triển thường dùng

```bash
# Upgrade module (xem thêm Readme.md)
odoo-bin -c conf/odoo.conf -d rental -u rental --stop-after-init
```

### Đường dẫn quan trọng

- Module: `custom_addons/odoo_modules/rental/`
- Services: `services/rental_contract_services.py`
- Security: `security/custom_security_groups.xml`, `ir_rule.xml`, `ir_model_access.xml`
- Migrations: `migrations/17.0.1.0.1/`, `17.0.1.0.2/`
