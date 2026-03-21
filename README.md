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

## Nhóm quyền

- **Spa / Phiếu lương (đọc)** — xem phiếu (read).
- **Spa / Phiếu lương (quản trị)** — tạo/sửa phiếu, wizard, duyệt làm thêm; kế thừa `spa.group_spa_manager`.

Gán nhóm trong **Cài đặt → Người dùng**.

## Cài đặt

```bash
./odoo-bin -c odoo.conf -d <database> -i spa_staff_payroll
```
