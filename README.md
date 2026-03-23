# Spa Staff Payroll (`spa_staff_payroll`)

## Phụ thuộc

- `spa` — thẻ, buổi trị liệu (`spa.treatment.session`), sản phẩm có trường **Lương nhân viên / 1 lần dịch vụ** (`service_employee_salary`).
- `booking_calendar` — đặt lịch, liên kết `booking_id` trên buổi (không bắt buộc cho logic lương: tính theo buổi `done`).
- `hr`, `hr_contract` — nhân viên, hợp đồng, lương cố định (`wage`), thêm trường **Lương làm thêm / giờ** trên hợp đồng.

> **Lưu ý:** `hr_payroll` (Odoo Payroll chuẩn) thường thuộc **Enterprise**. Module này dùng **phiếu lương tùy chỉnh** (`spa.staff.payroll`) tương thích Community.

## Nghiệp vụ

1. **Phiếu lương** (`spa.staff.payroll`): kỳ `date_from` → `date_to`, lương cố định, đơn giá làm thêm/giờ, thưởng, khấu trừ BH, khấu trừ khác, **tổng phải trả**.
2. **Tab dịch vụ:** các dòng từ `spa.treatment.session` có `state=done`, ngày buổi trong kỳ; tiền buổi = `service_employee_salary` trên **product.template** của dịch vụ buổi đó; **chia đều** cho các `therapist_ids` (nếu rỗng thì dùng `therapist_id`).
3. **Tab làm thêm:** tổng hợp `spa.staff.overtime.request` trạng thái **Đã duyệt** trong kỳ × đơn giá trên phiếu.
4. **Ngày nghỉ:** `spa.staff.dayoff` — hiển thị cắt giao kỳ (tham khảo).
5. **Đăng ký làm thêm:** nhân viên tạo → gửi duyệt → Manager/HR duyệt.

## Menu Spa → Lương NV

- **Nhân viên (HR)** — danh sách nhân viên (gắn User đăng nhập).
- **Hợp đồng lao động** — tạo hợp đồng trạng thái _Running_, lương, đơn giá làm thêm/giờ (nhóm quản trị phiếu lương).
- Wizard tạo phiếu theo tháng, phiếu lương, làm thêm giờ, ngày nghỉ.

## Nhóm quyền (mục **Spa** trên form người dùng)

- **Phiếu lương Spa (đọc)** — xem phiếu lương; kế thừa **Spa Staff** + **HR / Nhân viên** (đọc nhân viên).
- **Phiếu lương Spa (quản trị)** — tạo/sửa phiếu, wizard, hợp đồng, ngày nghỉ, duyệt làm thêm; kế thừa nhóm đọc + **Quản lý hợp đồng** (`hr_contract`).

**Spa Manager** được cấu hình tự kế thừa **Phiếu lương Spa (quản trị)** — user đã là Spa Manager sẽ thấy menu **Lương NV** sau khi upgrade module.

Gán thêm nhóm đọc/quản trị trong **Cài đặt → Người dùng → tab Quyền → nhóm Spa** (không nằm trong mục Nhân sự).

## Cài đặt

```bash
./odoo-bin -c odoo.conf -d <database> -i spa_staff_payroll
```
