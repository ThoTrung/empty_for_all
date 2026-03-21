# booking_calendar

Module Odoo 17: đặt lịch dịch vụ + lịch (calendar), tách từ `spa`.

## Phụ thuộc

- `spa` (thẻ trị liệu, giường/máy, sản phẩm composite, mixin hoàn thành đặt lịch trên thẻ, v.v.)

## Cài đặt

Thêm `booking_calendar` vào `addons_path`, cài module **sau** `spa` (hoặc cùng lúc).

```bash
./odoo-bin -d DB -i spa,booking_calendar
```

Nâng cấp từ bản gộp trong `spa`:

```bash
./odoo-bin -d DB -u spa,booking_calendar
```

### Cron nhắc lịch

Cron được định nghĩa trong module này (`booking_calendar`). Nếu DB cũ đã có cron từ `spa` (`spa_cron.xml` đã gỡ), có thể còn một bản ghi cron cũ: kiểm tra **Cài đặt → Kỹ thuật → Scheduled Actions** và tắt/xóa bản trùng nếu có.

### Chuỗi số (sequence)

`ir.sequence` cho `spa.service.booking` và `spa.booking.non_session_offering` vẫn nằm trong `spa/data/sequence_data.xml` để tránh trùng `code` khi nâng cấp.

## Models (tên kỹ thuật giữ nguyên)

- `spa.service.booking`, `spa.service.booking.line`
- `spa.booking.non_session_offering`
- `spa.recurring.booking.wizard`

Mở rộng `spa.treatment.card` / `spa.treatment.session` (trường `booking_*`) nằm trong module này để `spa` có thể chạy độc lập khi chưa cài đặt lịch.
# empty_for_all
