# Hình thức đặt lịch & hoàn thành (cách B)

## Giao diện nhân viên

- Trường **Hình thức lịch** (`booking_kind`): một dropdown.
  - **Sử dụng thẻ trị liệu** → chọn **Thẻ** (trừ buổi qua `spa.treatment.session` gắn thẻ).
  - **Không trừ buổi thẻ — họp, tư vấn, đi học…** → chọn **Loại hoạt động** (danh mục `spa.booking.non_session_offering`).

## Cách B (delegation)

- `completion_res_model_id` + `completion_res_id`: trỏ tới bản ghi xử lý hoàn thành (đồng bộ từ thẻ / loại hoạt động).
- `action_done` gọi `target.spa_complete_booking(booking)` (mixin `spa.booking.completion.mixin`).

## Mở rộng sau này

1. Thêm giá trị mới vào `Selection` của `booking_kind` trên `spa.service.booking`.
2. Thêm trường Many2one (hoặc cách chọn) tương ứng + `attrs` trên form.
3. Bổ sung nhánh trong `_compute_completion_pointer`.
4. Model đích inherit `spa.booking.completion.mixin` và triển khai `spa_complete_booking`.

Menu **Loại hoạt động không trừ buổi** (nhóm Spa Manager): chỉnh sửa danh mục loại hoạt động; nhân viên chỉ đọc.
