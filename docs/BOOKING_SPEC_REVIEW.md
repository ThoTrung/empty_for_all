# Đặc tả phần Đặt lịch (Spa Service Booking) – Bản review

Tài liệu này tổng hợp toàn bộ yêu cầu đã thống nhất về phần Đặt lịch để review lần cuối trước khi triển khai.

---

## 1. Đặt lịch trước theo ngày trong tuần (recurring by weekday)

### 1.1 Mô tả

- Cho phép **đặt lịch trước** theo **ngày trong tuần** (ví dụ: Thứ 2 và Thứ 6 hàng tuần).
- Hệ thống **tự động tạo** toàn bộ các bản ghi đặt lịch tương ứng với **số buổi còn lại** của dịch vụ (thẻ trị liệu).
- Ví dụ: Thẻ có 10 buổi, khách chọn Thứ 2 + Thứ 6 → hệ thống tạo 10 bản ghi đặt lịch (tuần 1 T2, tuần 1 T6, tuần 2 T2, tuần 2 T6, …) cho đến hết 10 buổi.

### 1.2 Trường bắt buộc / không bắt buộc trong luồng này

- **Bắt buộc khi tạo chuỗi:**
  - **Khách hàng** (partner)
  - **Thẻ trị liệu** (treatment card)
- **Không bắt buộc** (có thể để trống lúc tạo, điền sau hoặc theo chính sách khác):
  - **Nhân viên phụ trách** (staff)
  - **Giường / máy** (bed)

### 1.3 Giờ bắt đầu

- **Nhân viên chọn một lần** (ví dụ 9:00) khi tạo chuỗi.
- Giờ đó **áp dụng cho toàn bộ các buổi** trong chuỗi (mọi buổi trong chuỗi đều bắt đầu cùng giờ đã chọn).

### 1.4 Cần làm rõ (nếu có)

- Khoảng ngày áp dụng: từ ngày bắt đầu đến khi đủ số buổi, hay có thêm “đến ngày” tối đa?
- Có cần chọn thêm “giờ kết thúc” hay chỉ cần “giờ bắt đầu” + thời lượng mỗi buổi (lấy từ thẻ/dịch vụ)?

---

## 2. Dịch vụ cha – dịch vụ con (composite service)

### 2.1 Mô tả

- Có **dịch vụ** là **dịch vụ tổng** (dịch vụ cha), bên trong gồm **nhiều dịch vụ con**.
- Mỗi dịch vụ con có:
  - **Thời lượng riêng** (số phút/giờ).
  - **Nhân viên riêng** (người thực hiện phần đó).
- Mục đích sau này: **tính lương** cho nhân viên dựa trên từng dịch vụ (con) mà họ đã làm.

### 2.2 Cách tạo và sắp xếp dịch vụ con

- Khi nhân viên tạo **dịch vụ tổng** (dịch vụ cha), họ **được phép thêm các dịch vụ con** vào trong.
- **Thứ tự** dịch vụ con **tự do**: nhân viên **kéo thả / sắp xếp** (cần lưu `sequence` để hiển thị và tính thời gian đúng thứ tự).

### 2.3 Cấu trúc dữ liệu đặt lịch

- **Một đặt lịch** = **một bản ghi đặt lịch** (ứng với dịch vụ cha), bên trong có **nhiều dòng** (mỗi dòng = một dịch vụ con: thời lượng, nhân viên gán, có thể thời điểm bắt đầu/kết thúc).
- **Lợi ích**: giao diện đơn giản cho nhân viên – chỉ làm việc với “một đặt lịch”.
- **Trách nhiệm hệ thống**: khi **kiểm tra nhân viên có rảnh không** (và kiểm tra capacity %), hệ thống **phải xét từng dịch vụ con** (từng dòng): khoảng thời gian + nhân viên gán cho từng dòng, rồi tổng hợp để không bị trùng lịch / vượt capacity. Tức logic “rảnh / bận / %” tính ở **cấp dòng con**, không chỉ ở bản ghi cha.

---

## 3. Capacity % – một nhân viên làm nhiều dịch vụ trong cùng khung giờ

### 3.1 Mô tả

- Một số dịch vụ **chỉ chiếm một phần** năng lực nhân viên trong khung giờ (ví dụ 20%, 30%, 90%).
- Trong **cùng một khung thời gian**, **tổng %** các đặt lịch gán cho **cùng một nhân viên** không được vượt quá **100%**.
- Nếu còn đủ “chỗ” (100% − tổng % hiện tại) thì nhân viên đó **vẫn được chọn** cho đặt lịch mới.

### 3.2 Ví dụ

- Dịch vụ A = 20%, B = 30%, C = 90%.
- Nhân viên K đã có lịch dịch vụ A (20%) trong khung 9h–10h.
  - Đặt lịch mới trong 9h–10h, dịch vụ B (30%): **được phép** chọn K (20% + 30% = 50% ≤ 100%).
  - Đặt lịch mới trong 9h–10h, dịch vụ C (90%): **không được** chọn K (20% + 90% = 110% > 100%) → hệ thống **ẩn** (hoặc disable) nhân viên K trong danh sách chọn.

### 3.3 Yêu cầu kỹ thuật

- Mỗi **dịch vụ** có trường **“staff capacity %”** (hoặc tên tương đương), mặc định có thể 100% cho dịch vụ thông thường.
- Khi chọn nhân viên cho đặt lịch (hoặc cho từng dòng dịch vụ con), hệ thống:
  - Tính **tổng %** đã được gán cho nhân viên đó trong **cùng khung thời gian** (bao gồm cả các dòng con nếu là dịch vụ cha).
  - Chỉ **hiển thị / cho chọn** những nhân viên còn đủ % (tổng sau khi cộng thêm ≤ 100%).

### 3.4 Cần làm rõ (nếu có)

- Khung thời gian “trùng”: so sánh theo từng slot cố định (ví dụ 30 phút) hay theo đúng `start_datetime`–`end_datetime` của từng đặt lịch/dòng con?
- Dịch vụ con có thể có capacity % riêng hay luôn lấy từ dịch vụ con (sản phẩm)?

---

## 4. Gợi ý nhân viên theo luân chuyển (rotation) và cấp độ

### 4.1 Cấp độ nhân viên và dịch vụ

- **Nhân viên** có **cấp độ** (ví dụ: **Chuyên gia**, **Nhân viên**).
- **Dịch vụ** có **yêu cầu cấp độ** (ví dụ: “Chỉ chuyên gia” hoặc “Nhân viên trở lên”).
- Có những dịch vụ **chỉ nhân viên cấp Chuyên gia** mới được làm.

### 4.2 Luân chuyển theo cấp độ

- **Vòng luân chuyển** không phải toàn công ty/chi nhánh, mà **theo nhóm đủ cấp độ** với dịch vụ đó:
  - Khi đặt lịch cho một dịch vụ, hệ thống chỉ gợi ý / luân chuyển trong nhóm nhân viên **đủ cấp độ** (ví dụ dịch vụ yêu cầu Chuyên gia → chỉ luân giữa các Chuyên gia).
- **Quy tắc luân chuyển**: ví dụ 3 nhân viên X, Y, Z đủ cấp độ → đặt lịch thứ 1 gợi ý X, thứ 2 gợi ý Y, thứ 3 gợi ý Z, thứ 4 lại X, …
- **Điều kiện bổ sung**: Nhân viên được gợi ý phải **còn trống** trong khung thời gian (chưa vượt capacity %). Nếu đúng lượt là X nhưng X đang bận (hoặc không đủ %), hệ thống **bỏ qua X** và gợi ý **người tiếp theo trong vòng** (Y, Z, …) mà **còn available**.

### 4.3 Tóm tắt

- **Luân chuyển** = theo **cấp độ dịch vụ**: với mỗi dịch vụ, lọc nhân viên đủ cấp độ → luân chuyển trong nhóm đó; nếu người đúng lượt bận thì gợi ý người tiếp theo trong nhóm còn rảnh.

### 4.4 Cần làm rõ (nếu có)

- Thứ tự X, Y, Z trong vòng: cố định (theo ID, theo nhóm) hay admin cấu hình thứ tự ưu tiên?
- Cấp độ: có bao nhiêu cấp (Chuyên gia / Nhân viên hay thêm cấp khác)? Dịch vụ chọn “Chuyên gia” = chỉ Chuyên gia, “Nhân viên” = cả hai?

---

## 5. Tóm tắt tổng thể

| #   | Chủ đề                        | Nội dung chính                                                                                                                                                                                                |
| --- | ----------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Đặt lịch theo ngày trong tuần | Chọn ngày trong tuần (vd T2, T6) + giờ bắt đầu (chọn 1 lần cho cả chuỗi) → tự tạo đủ số buổi theo thẻ. Chỉ bắt buộc: Khách hàng, Thẻ trị liệu. NV + Giường không bắt buộc.                                    |
| 2   | Dịch vụ cha – con             | Dịch vụ cha chứa nhiều dịch vụ con; mỗi con có thời lượng + nhân viên; thứ tự kéo thả. Một đặt lịch = một bản ghi + nhiều dòng con. Check rảnh/capacity ở từng dòng con. Sau này tính lương theo dịch vụ con. |
| 3   | Capacity %                    | Mỗi dịch vụ có % chiếm dụng NV; trong cùng khung giờ tổng % ≤ 100%; ẩn NV không đủ % khi chọn.                                                                                                                |
| 4   | Luân chuyển + cấp độ          | NV có cấp độ; dịch vụ có yêu cầu cấp độ. Gợi ý theo vòng trong nhóm đủ cấp độ; nếu người đúng lượt bận → gợi ý người tiếp theo còn rảnh.                                                                      |

---

## 6. Checklist review

- [ ] Đặt lịch theo ngày trong tuần: đủ ý (bắt buộc/không bắt buộc, giờ áp dụng cả chuỗi)?
- [ ] Dịch vụ cha – con: thứ tự kéo thả, một đặt lịch một bản ghi nhiều dòng, check ở dòng con?
- [ ] Capacity %: dịch vụ có %, tổng ≤ 100%, ẩn NV không đủ %?
- [ ] Luân chuyển: theo cấp độ dịch vụ, trong nhóm đủ cấp độ, bỏ qua người bận?
- [ ] Các điểm “Cần làm rõ” ở trên: cần bổ sung hay chấp nhận để triển khai sau?

Sau khi bạn review và chỉnh sửa (nếu có), bản này sẽ dùng làm cơ sở để thiết kế model và luồng triển khai.


