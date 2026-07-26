# Spa Staff Payroll (`spa_staff_payroll`)

> Living doc cho Agent: [`docs/AGENT_REFERENCE.md`](docs/AGENT_REFERENCE.md) (kèm BUG_LOG / DECISIONS / WORKLOG).

Bậc mặc định (KPI / ca dài / khách đặt / giải thưởng) load khi **cài hoặc upgrade** module (`data/spa_payroll_default_tiers_data.xml`, `noupdate`): `company_id` trống = mọi công ty; sửa tay sau **không** bị ghi đè khi `-u`. Wizard **Nạp bậc lương mặc định** vẫn idempotent nếu cần bổ sung.

## Phụ thuộc

- `spa` — thẻ, buổi trị liệu (`spa.treatment.session`), sản phẩm có trường **Lương nhân viên / 1 lần dịch vụ** (`service_employee_salary`).
- `booking_calendar` — đặt lịch, liên kết `booking_id` trên buổi (không bắt buộc cho logic lương: tính theo buổi `done`).
- `hr`, `hr_contract` — nhân viên, hợp đồng, lương cố định (`wage`), thêm trường **Lương làm thêm / giờ** trên hợp đồng.
- `account` — dùng để tính **KPI doanh thu** và **hoa hồng bán hàng** theo hóa đơn đã thu tiền / SO đã settled.
- `sale` — đơn bán: HH khi SO thu đủ (Số tiền còn lại / residual HĐ = 0).

> **Lưu ý:** `hr_payroll` (Odoo Payroll chuẩn) thường thuộc **Enterprise**. Module này dùng **phiếu lương tùy chỉnh** (`spa.staff.payroll`) tương thích Community.

## Nghiệp vụ

1. **Phiếu lương** (`spa.staff.payroll`): kỳ `date_from` → `date_to`, lương cố định (**chia theo số ngày HĐ giao với kỳ**), đơn giá làm thêm/giờ, thưởng, khấu trừ BH, khấu trừ khác, **tổng phải trả**.
2. **Các nguồn dữ liệu chính**:
   - **Buổi làm**: `spa.treatment.session` trạng thái `done` trong kỳ.
   - **Làm thêm**: `spa.staff.overtime.request` trạng thái **Đã duyệt** trong kỳ.
   - **KPI/Hoa hồng bán**: SO **settled** (đã xuất đủ HĐ, residual = 0) hoặc HĐ không gắn SO đã `paid`; kỳ theo **ngày đủ tiền** (không theo ngày lập HĐ).
3. **Tab «Lương»**: lương cứng (prorate) + tổng hợp tiền + ledger `line_ids` (**1 dòng / loại**: tiền công buổi, thưởng ca, KPI, hoa hồng, ăn trưa…). Chi tiết xem tab **Buổi làm** / **Hoa hồng SP** / **KPI** / **Làm thêm** / Ngày nghỉ.

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

## Hướng dẫn thao tác cho nhân viên (làm theo từng bước)

### 1) Tạo nhân viên

Vào **Spa → Lương NV → Nhân viên (HR)** (hoặc luồng tạo nhân viên khác trên hệ thống của bạn, ví dụ từ **Người dùng**).

Mỗi nhân viên cần tối thiểu:

- Tên nhân viên
- **User** (`user_id`): bắt buộc để hệ thống khớp dữ liệu
  - Buổi làm theo `spa.treatment.session.therapist_ids`
  - KPI/hoa hồng bán theo `account.move.invoice_user_id`

> Nếu nhân viên vừa làm dịch vụ vừa bán hàng: vẫn dùng 1 user, hệ thống sẽ tính cả 2 phần.

### 2) Tạo hợp đồng cho nhân viên (cài đặt thông tin gì)

Vào **Spa → Lương NV → Hợp đồng lao động**.

Tạo 1 hợp đồng trạng thái **Running/Open** cho từng nhân viên và nhập:

- **Employee**: nhân viên
- **Date Start** (và Date End nếu có)
- **Wage**: lương cố định/tháng
- **Lương làm thêm / giờ** (`spa_overtime_hourly_rate`): dùng để tính OT trong kỳ

Trên form hợp đồng, module đã **ẩn tạm** các nhóm trường không tham gia tính phiếu lương Spa (loại cấu trúc lương, phòng ban, chức vụ, kiểu HĐ, lịch làm việc trên form, tab **Chi tiết hợp đồng**). Trường **Ghi chú** (`notes`) được đưa xuống ngay **dưới Ngày kết thúc hợp đồng**. Các giá trị ẩn vẫn có thể được điền mặc định từ công ty/nhân viên ở backend; **không cần thêm trường mới** trên hợp đồng cho spec lương Spa hiện tại.

### 3) Chuẩn bị sản phẩm dịch vụ (để tính tiền công theo buổi)

Vào **Sản phẩm** (`product.template`) và đảm bảo các dịch vụ có:

- **Số buổi / đơn vị** (`spa_sessions_per_unit`) nếu muốn trả theo % “giá 1 buổi”
- **Lương nhân viên / 1 lần dịch vụ** (`service_employee_salary`) nếu muốn trả cố định theo dịch vụ

Nếu trả theo cấu hình profile payout (fixed + %):

- Tạo **Profile trả lương dịch vụ** (`spa.product.payroll.profile`)
- **Công ty** tùy chọn: để trống = **mọi công ty** đều gắn được profile này
- Thêm dòng theo **cấp nhân viên** (`spa.staff.level`): `amount_fixed`, `percent`
- Gắn profile vào `product.template.spa_payroll_profile_id`

**Cách tính % (theo nghiệp vụ đã chốt):**

\[
\text{giá 1 buổi} = \frac{\text{list\_price}}{\text{spa\_sessions\_per\_unit}}
\]

Nếu `spa_sessions_per_unit` = 0 thì dùng `list_price`.

### 4) Nhập thông tin ca dài / khách chủ động đặt (trên buổi làm)

Trên **buổi làm** `spa.treatment.session` (state `done`) có 2 trường:

- `spa_payroll_shift_kind`: Ca ngắn / Ca dài
- `spa_payroll_customer_requested`: Khách chủ động đặt
  - Calendar (`draft`/`confirmed`): màu ICP `spa.booking_calendar_hex_color_customer_requested` (default `#FF8C00`), ghi đè draft-special
  - Constraint: tick ⇒ bắt buộc `staff_ids` (booking đơn) / `staff_id` (line)

Các trường này dùng để tính:

- **Thưởng ca dài**
- **Thưởng khách chủ động đặt** (chỉ đếm trong ca dài)

### 5) (Tuỳ chọn) Cấu hình KPI và hoa hồng bán hàng

- **Bậc thưởng ca dài / khách đặt / KPI** (`spa.payroll.*.tier`): trường **Công ty** là **tùy chọn**. Để trống = áp dụng **mọi công ty**; nếu có cùng loại bậc cho một công ty cụ thể, hệ thống **ưu tiên bậc theo công ty** hơn bậc chung.
- **KPI**: cấu hình bậc tại `spa.payroll.kpi.revenue.tier`.
  - KPI lấy doanh thu **cash-basis**: SO settled trong kỳ (theo ngày đủ tiền) + HĐ lẻ đã paid; salesperson = `sale.order.user_id` / `invoice_user_id`.
- **Hoa hồng**: nhập `%` tại **Danh mục sản phẩm** (`product.category.spa_sales_commission_percent`).
  - Danh mục con để 0 → hệ thống leo lên danh mục cha.
  - Field `%` trên từng sản phẩm đã ẩn (legacy, không dùng khi tính).
  - **Hoàn thành để tính HH**: SO đã trả hết (`amount_to_invoice ≈ 0` và mọi HĐ gắn SO `amount_residual ≈ 0`). Đặt cọc → chưa tính; trả đủ → tính toàn đơn vào tháng đủ tiền.
  - Base = `price_subtotal` dòng SO/HĐ (**sau CK dòng**). CK toàn đơn: nên phân bổ vào dòng trước khi chốt.

### 6) Tạo phiếu lương (kỳ tháng) và tính lương

Vào **Spa → Lương NV → Phiếu lương**.

Tạo phiếu và nhập:

- **Nhân viên**
- **Từ ngày** (`date_from`) / **Đến ngày** (`date_to`)

Sau đó:

1. Bấm **Nạp hợp đồng** (để lấy lương cố định + đơn giá OT).
2. Bấm **Tính các khoản** để hệ thống tạo/refresh các dòng ledger trên tab **Lương**:
   - Tiền công theo buổi (`service_payout_session` — 1 dòng tổng; chi tiết tab Buổi làm)
   - Thưởng ca dài / khách chủ động đặt
   - KPI doanh thu / hoa hồng bán
   - Hỗ trợ ăn trưa (theo tổng phút buổi làm/ngày trong kỳ)
3. Nếu cần, thêm dòng **Điều chỉnh / Ghi chú** (nhập tay).
4. Kiểm tra **Tổng phải trả**.
5. Khi chốt, bấm **Xác nhận** để khóa phiếu (không cho tính lại).

## Vận hành & lưu ý

- **Chốt dữ liệu**: sau khi phiếu lương `done`, không cho recompute để tránh thay đổi số liệu.
- **Hiệu năng**: kỳ dài và nhiều session/hóa đơn sẽ đọc nhiều dữ liệu; nên chạy theo tháng và theo từng nhân viên.
- **Làm thêm giờ**: yêu cầu OT phải ở trạng thái đã duyệt mới lên phiếu.

## Troubleshooting

- **Bấm “Tính các khoản” không ra tiền công buổi**:
  - Kiểm tra session có `state=done` và `date` nằm trong kỳ.
  - Kiểm tra session có nhân viên trong `therapist_ids`.
  - Kiểm tra session có `product_id` (thường lấy từ card).
- **KPI/hoa hồng = 0**:
  - SO chưa thu đủ (còn residual) hoặc HĐ lẻ chưa `paid`.
  - Ngày đủ tiền không nằm trong kỳ phiếu (VD HĐ tháng 5, trả tháng 7 → HH tháng 7).
  - Kiểm tra `user_id` trên SO / `invoice_user_id` trên HĐ đúng NV bán.
  - Kiểm tra `% thưởng bán hàng` trên **danh mục** sản phẩm (hoặc danh mục cha).
  - Kiểm tra `spa_sales_commission_percent` trên danh mục (field trên SP đã ẩn).

