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

## 2026-06-05 — Import xuất nhập kho: picking + biểu mẫu + lỗi SP chi tiết

- Author/agent: Cursor agent
- Task: Cho phép import lại vận chuyển cũ (không chặn trùng trên HĐ); option xác nhận picking; nút tải biểu mẫu; lỗi mapping SP chi tiết (cột, gợi ý tên Odoo).
- Files touched:
  - `helper/import_transport_matrix.py`, `models/transport.py`
  - `wizard/rental_transport_import_wizard.py`, `wizard/rental_transport_import_wizard.xml`
  - `controllers/rental_contract_controller.py`, `models/rental_contract.py`
  - `tests/test_transport_import.py`, `docs/DECISIONS.md`
- Validation: cập nhật unit tests (chưa chạy odoo-bin).

---

## 2026-06-05 — Import xuất nhập kho từ Excel

- Author/agent: Cursor agent
- Task: Wizard import ma trận khối lượng → `rr.transport` trên tab Transports; cột C biển số; qty âm = nhập; trùng ngày+biển số trong file báo lỗi.
- Files touched:
  - `helper/import_transport_matrix.py`
  - `wizard/rental_transport_import_wizard.py`, `wizard/rental_transport_import_wizard.xml`
  - `models/rental_contract.py`, `views/rental_contract_view.xml`
  - `security/ir_model_access.xml`, `__manifest__.py`
  - `tests/test_transport_import.py`, `docs/DECISIONS.md`
- Validation: `tests/test_transport_import.py` (chưa chạy odoo-bin trong phiên này).
- Notes: Không tự tạo picking; cần tài xế mặc định trên wizard.

---

## 2026-06-04 — Nhân viên upload mẫu tài liệu tải xuống

- Author/agent: Cursor agent
- Task: Cho phép Rental Staff quản lý file mẫu (DOCX/XLSX) trên menu «Mẫu tài liệu cho thuê»; gom logic `get_template_bytes` trên `rental.template`.
- Files touched:
  - `models/rental_template.py`, `views/rental_template_view.xml`, `views/menu.xml`
  - `security/ir_model_access.xml`, `security/ir_rule.xml`
  - `services/rental_contract_services.py`, `models/rental_contract.py`
  - `controllers/rental_contract_controller.py`, `controllers/rental_transport_controller.py`
  - `migrations/17.0.1.0.20/post-migrate.py`, `__manifest__.py`
- Validation: `-u rental` trên Docker.
- Notes: Mỗi loại mẫu + công ty có thể nhiều bản ghi; chỉ một bản `Mặc định` / loại.

---

## 2026-06-04 — Fix bảng xác nhận khối lượng + bảng thanh toán (bằng chữ)

- Author/agent: Cursor agent
- Task: Sửa 4 bug báo cáo: (1) cột HTML đè nhau, (2) Tổng MD cho SP mét dài 1 biến thể, (3) Excel ma trận mất format cột cuối, (4) tiền bằng chữ sai trên bảng thanh toán.
- Files touched:
  - `models/rental_transport_matrix.py`
  - `controllers/rental_contract_controller.py`
  - `helper/export_excel_template.py`
  - `models/rental_contract.py`
  - `static/file_template/rental_invoice_template.xlsx`
  - `tests/test_rental_transport_matrix_overlap.py`
  - `docs/BUG_LOG.md`
- Validation: Unit tests mới cho `_group_needs_md_column`; chưa chạy `odoo-bin --test-enable` (môi trường local thiếu pip/DB).
- Notes / follow-up:
  - Upgrade module: `odoo-bin -u rental`
  - Công ty dùng `rental.template` custom cho invoice/matrix cần thêm placeholder `{{total_after_tax_string}}` nếu chưa có.

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
