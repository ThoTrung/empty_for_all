# Bảng màu lịch (Calendar) – Chỉ số 0–55

Bảng dưới đây map **số (0–55)** với **màu** dùng trên lịch đặt lịch (Odoo Web calendar palette). Dùng khi cấu hình **Cấu hình → Spa → Màu lịch đặt lịch** theo trạng thái.

| Số  | Hex     | Mô tả          | Số  | Hex     | Mô tả        | Số  | Hex     | Mô tả          |
| --- | ------- | -------------- | --- | ------- | ------------ | --- | ------- | -------------- |
| 0   | #a2a2a2 | Xám nhạt       | 19  | #173e43 | Xanh lục đen | 38  | #8cff00 | Xanh lá chanh  |
| 1   | #ee2d2d | Đỏ             | 20  | #348F50 | Xanh lá cây  | 39  | #00f2ff | Xanh cyan      |
| 2   | #dc8534 | Cam            | 21  | #AA3A38 | Đỏ nâu       | 40  | #004ab3 | Xanh dương đậm |
| 3   | #e8bb1d | Vàng           | 22  | #795548 | Nâu đồng     | 41  | #ff00d0 | Hồng tươi      |
| 4   | #5794dd | Xanh dương     | 23  | #5e0231 | Đỏ tía đậm   | 42  | #ffa600 | Cam vàng       |
| 5   | #9f628f | Tím hoa cà     | 24  | #6be585 | Xanh lá sáng | 43  | #3acc00 | Xanh lá        |
| 6   | #db8865 | Cam nâu        | 25  | #999966 | Xanh xám     | 44  | #00b6bf | Xanh lục biển  |
| 7   | #41a9a2 | Xanh lục biển  | 26  | #e9d362 | Vàng đồng    | 45  | #0048ff | Xanh dương     |
| 8   | #304be0 | Xanh dương đậm | 27  | #b56969 | Hồng nâu     | 46  | #bf7c00 | Vàng nâu       |
| 9   | #ee2f8a | Hồng           | 28  | #bdc3c7 | Xám bạc      | 47  | #04ff00 | Xanh lá neon   |
| 10  | #61c36e | Xanh lá        | 29  | #649173 | Xanh rêu     | 48  | #00d0ff | Xanh cyan      |
| 11  | #9872e6 | Tím            | 30  | #ea00ff | Magenta      | 49  | #0036bf | Xanh dương đậm |
| 12  | #aa4b6b | Đỏ tía         | 31  | #ff0026 | Đỏ tươi      | 50  | #ff008c | Hồng đậm       |
| 13  | #30C381 | Xanh lá đậm    | 32  | #8bcc00 | Xanh lá tươi | 51  | #00bf49 | Xanh lá        |
| 14  | #97743a | Nâu            | 33  | #00bfaf | Xanh ngọc    | 52  | #0092b3 | Xanh biển      |
| 15  | #F7CD1F | Vàng chanh     | 34  | #006aff | Xanh dương   | 53  | #0004ff | Xanh dương     |
| 16  | #4285F4 | Xanh Google    | 35  | #af00bf | Tím magenta  | 54  | #b20062 | Đỏ tía         |
| 17  | #8E24AA | Tím đậm        | 36  | #bf001d | Đỏ đậm       | 55  | #649173 | Xanh rêu       |
| 18  | #D6145F | Đỏ hồng        | 37  | #bf6300 | Cam đậm      |     |         |                |

## Gợi ý cho trạng thái đặt lịch

- **Đặt lịch (draft):** 1 (đỏ), 2 (cam), 3 (vàng) – chưa xác nhận
- **Đã xác nhận (confirmed):** 4 (xanh dương), 16 (xanh Google)
- **Đang phục vụ (doing):** 10 (xanh lá), 13 (xanh lá đậm), 43
- **Đã hoàn thành (done):** 7 (xanh lục biển), 20 (xanh lá cây)
- **Đã hủy (cancel):** 0 (xám), 28 (xám bạc)

Nguồn palette: `odoo/addons/web/static/src/scss/secondary_variables.scss` (`$o-colors` + `$o-colors-secondary`).
