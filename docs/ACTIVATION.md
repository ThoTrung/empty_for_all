# Kích hoạt Zalo OA / ZNS (nhắc lịch)

Chỉ gửi **nhắc lịch hẹn** (lịch **Đã xác nhận**). Demo trước, rồi production **với whitelist 1–2 SĐT** cho đến khi ổn.

Hai công tắc độc lập:

- **Whitelist:** cron nhắc lịch chỉ enqueue SĐT trong danh sách. Lịch khác **không** bị đánh «Đã nhắc KH qua Zalo».
- **Gửi thử (development):** `mode=development` trên API Zalo — chỉ **admin OA/App** nhận tin. SĐT khách thường → `-127`.

Trên production smoke với 1–2 số khách thật: **tắt development**, **bật whitelist**, rồi mới bật nhắc lịch.

## Luật Zalo cần nhớ

- Access token OA ~25 giờ (`expires_in` từ API). Refresh token ~3 tháng, **dùng 1 lần**; mỗi lần làm mới Zalo cấp refresh mới, cái cũ chết.
- Gửi ZNS: `POST https://business.openapi.zalo.me/message/template` — SĐT `84…` đã có Zalo, template đã duyệt, `template_data` đúng **tập khóa** mẫu, `tracking_id` ≤48 alphanumeric.
- **Không gửi 22:00–06:00 giờ VN** (mã `-133`). Odoo hoãn hàng đợi.
- `mode=development`: chỉ **admin OA/App** nhận tin, không tính phí. SĐT khách thường → `-127`.
- Không ủy quyền API Explorer lần hai khi Odoo đang giữ refresh còn sống.

Tài liệu: [Ủy quyền AppID](https://zalo.solutions/business-message/guidelines/huong-dan-uy-quyen-oa-cho-ung-dung-appid), [Gửi ZNS](https://developers.zalo.me/docs/api/zalo-notification-service-api/gui-zns/gui-zns-post-5208), [Development mode](https://developers.zalo.me/docs/api/zalo-notification-service-api/gui-zns/gui-zns-su-dung-development-mode-post-5206).

## B0. Điều kiện ngoài Odoo

1. OA xác thực, gói gửi tin; ví ZBA còn tiền.
2. App trên [developers.zalo.me](https://developers.zalo.me/) — App ID + App Secret.
3. App đã liên kết OA (và ZBS nếu Zalo yêu cầu).
4. Bạn là quản trị viên **cả OA lẫn App**.
5. SĐT demo (B4–B6) = admin OA hoặc admin App. SĐT smoke prod (B7) có thể là khách thật — khi đó phải tắt development.
6. Thử **06:00–22:00** giờ VN.

## B1. Mẫu ZNS nhắc lịch

1. OA / ZBS → mẫu tin ZNS/ZBS Template.
2. Ưu tiên biến: `name`, `date`, `time`, `service`. Tên khác → điền JSON map ở B4.
3. Chờ duyệt ENABLE. Copy Template ID.

## B2. Token lần đầu (API Explorer)

1. [Zalo API Explorer](https://developers.zalo.me/tools/explorer).
2. Loại token: **OA Access Token**, đúng App, chọn OA, Cho phép.
3. Copy **access_token** và **refresh_token**.

## B3. Dán vào Odoo (máy dev / `drlai`)

```bash
source /home/tho/project/17.0/venv/bin/activate
python3 ./odoo/odoo-bin -c ./conf/odoo_dev.conf -d drlai \
  --addons-path=odoo/addons,custom_addons \
  -u spa_zalo_oa --stop-after-init --http-port=8090
```

Spa → **Zalo OA → Tài khoản Zalo OA** (Clic Administrator): App ID, App Secret, Refresh Token → **Làm mới token**. `last_error` phải trống.

Cron «Zalo OA: Làm mới access token» phải bật. Không copy refresh_token từ máy đã từng bấm Làm mới sang máy khác.

## B4. Cấu hình demo (`drlai`)

Cấu hình Spa → Zalo ZNS:

- Template ID; map khóa trống nếu mẫu dùng `name/date/time/service`.
- **Gửi thử (development):** BẬT.
- **Whitelist:** BẬT, chỉ SĐT admin OA/App.
- **Bật nhắc lịch** sau cùng.

## B5. Gửi thử 1 tin

1. KH test với SĐT admin.
2. **Tin Zalo (ZNS)** → tạo tin nhắc lịch + JSON mẫu → **Gửi ngay** (ban ngày).
3. Trạng thái **Đã gửi**, điện thoại nhận ZNS.

Nút **Gửi ngay** / hàng đợi cũng **không gửi** SĐT ngoài whitelist khi whitelist đang bật.

Lỗi thường gặp: `-112` sai/thừa biến; `-127` không phải admin / còn bật development; `-124` token; `-131` chưa duyệt; `-118` không có Zalo; `-133` đêm.

## B6. Luồng lịch (demo)

1. Booking **Đã xác nhận**, giờ trong cửa sổ nhắc, SĐT whitelist.
2. Cron 15 phút (nhắc) + 5 phút (hàng đợi), hoặc Technical → Cron chạy tay.
3. Cờ «Đã nhắc KH qua Zalo»; tin `sent`.
4. Lịch nháp không tạo tin; ngoài whitelist không đánh dấu đã nhắc.

## B7. Production — whitelist 1–2 SĐT (làm ngay lúc deploy)

Thứ tự bắt buộc: backup → code → token/template → **tắt development** → **bật whitelist + 1–2 SĐT** → **mới bật nhắc lịch**.

ICP mặc định lúc cài lần đầu: `reminder_enabled=0` (cron chưa gửi), `development_mode=1`, `whitelist_enabled=0`. An toàn cho đến khi bật nhắc lịch. Nếu bật nhắc mà quên whitelist thì cron gửi **mọi** lịch confirmed trong cửa sổ.

### B7.1 Backup và đưa code

1. Backup DB production.
2. Sync cả thư mục `custom_addons/spa_zalo_oa` (version `17.0.1.1.1`, depends `spa` + `booking_calendar`).
3. Upgrade (đổi `-c` / `-d` đúng prod):

```bash
# module đã cài
odoo-bin -c <odoo.conf prod> -d <DB_PROD> -u spa_zalo_oa --stop-after-init

# chưa cài
odoo-bin -c <odoo.conf prod> -d <DB_PROD> -i spa_zalo_oa --stop-after-init
```

4. Restart workers.

**Không** copy `refresh_token` từ `drlai` nếu máy test đã từng bấm Làm mới token. Lấy token **mới trên prod** (B2) một lần.

### B7.2 Cấu hình — lưu trước khi bật nhắc

Clic Administrator → **Zalo OA → Tài khoản Zalo OA**: App ID, App Secret, Refresh Token → **Làm mới token**. `last_error` trống, có `token_expiry`.

Cấu hình Spa → **Zalo ZNS**:

| Cài đặt | Giá trị lúc smoke prod |
|---|---|
| Template ID nhắc lịch | ID mẫu đã duyệt |
| Map khóa JSON | trống hoặc đúng khóa mẫu |
| Nhắc trước | 2 giờ (hoặc N đang dùng) |
| Gửi thử (development) | **TẮT** nếu 1–2 số không phải admin OA |
| Chế độ whitelist | **BẬT** |
| SĐT whitelist | 1–2 số, có Zalo, ví dụ `090xxxxxxx, 091xxxxxxx` |
| Bật nhắc lịch KH | **BẬT sau cùng** |

Cron (Technical → Scheduled Actions) phải active:

- Zalo OA: Làm mới access token (12 giờ)
- Zalo OA: Nhắc lịch hẹn khách hàng (ZNS) (15 phút)
- Zalo OA: Gửi hàng đợi tin ZNS (5 phút)

### B7.3 Smoke chỉ 1–2 số

1. KH Odoo có **mobile/phone đúng** số whitelist (0xx hoặc 84 đều được).
2. Tạo lịch **Đã xác nhận**, giờ hẹn trong cửa sổ nhắc (vd nhắc trước 2 giờ → hẹn trong 2 giờ tới). Lịch nháp không gửi.
3. Đợi cron hoặc chạy tay: nhắc lịch, rồi hàng đợi. Chỉ ban ngày (06:00–22:00 VN).
4. Kiểm tra: cờ **Đã nhắc KH qua Zalo**; **Tin Zalo (ZNS)** → `sent` + `zalo_msg_id`; điện thoại nhận ZNS.
5. Lịch khách **không** whitelist: không có tin, không bị đánh đã nhắc.

## B8. Khi đã ổn — mới mở hết khách (không làm lúc deploy)

Chỉ sau khi B7.3 `sent` và điện thoại nhận được:

1. Giữ **development TẮT**.
2. Tắt **whitelist** → Save.
3. Smoke 1 lịch confirmed SĐT thật **ngoài** danh sách cũ → `sent`.
4. **Không** ủy quyền API Explorer lại khi Odoo đang giữ refresh còn sống.
