# Hướng dẫn sử dụng — Thuê ngoài (Rental Subrent)

Module: `rental_subrent` · Menu gốc: **Cho thuê → Thuê ngoài**

Tài liệu này dành cho nhân viên điều phối / kho và quản lý. Giải thích từng bước thao tác trên Odoo.

---

## 1. Chuẩn bị

### 1.1. Cài module

1. Apps → tìm **Rental Subrent** (hoặc cài qua `-i rental_subrent`).
2. Module phụ thuộc **Rental** đã cài và cập nhật.

### 1.2. Phân quyền

Vào **Settings → Users → Users**, mở user cần dùng:

| Group | Ai dùng | Được làm gì |
|---|---|---|
| **Thuê ngoài — Nhân viên** | Điều phối / kho | HĐ NCC, nhận/trả, sổ lô, tình trạng SP, panel thiếu hàng |
| **Thuê ngoài — Quản lý** | Quản lý | Thêm: giá NCC, công nợ tháng, margin, đối soát kho TN |

User cần có quyền Cho thuê (Staff) vì group Nhân viên thuê ngoài kéo theo Staff.

Sau khi gán quyền, **đăng xuất / đăng nhập lại** (hoặc hard refresh) để thấy menu **Thuê ngoài**.

---

## 2. Tạo nhà cung cấp (NCC)

Menu: **Cho thuê → Thuê ngoài → NCC thuê ngoài**

1. Bấm **New** (hoặc mở danh sách rồi tạo mới).
2. Điền tên công ty / thông tin liên hệ.
3. Checkbox **NCC** đã được bật sẵn — giữ nguyên. Có thể tick thêm **Khách thuê** nếu NCC cũng thuê hàng của mình (giá NCC↔NCC).
4. Lưu.

Chỉ partner có cờ **NCC** mới chọn được trên HĐ thuê ngoài; cờ **Khách thuê** để chọn trên HĐ thuê khách.

Trên form partner:
- Tab **Hợp đồng thuê** chỉ hiện khi tick **Khách thuê**.
- Tab **Hợp đồng với NCC** chỉ hiện khi tick **NCC** — từ đây tạo HĐ thuê ngoài (mặc định chế độ đơn giản).

*(Cách cũ: mở Contacts bất kỳ và tick «NCC» — vẫn dùng được.)*

---

## 3. Tạo hợp đồng thuê ngoài

Menu: **Cho thuê → Thuê ngoài → HĐ thuê ngoài → New**

### Bước 3.1 — Thông tin chung

1. Chọn **NCC** (tab **Thông tin cơ bản**); có thể chọn **Đại diện NCC** / **Đại diện bên ta**.
2. Điền **Ngày hợp đồng** / **Số HĐ trên giấy** (tuỳ chọn; khác mã hệ thống).
3. Chọn **Chế độ quản lý** (xem mục 4–6; mặc định **Đơn giản — nhập kho mình**).
4. Điền ngày bắt đầu / kết thúc dự kiến (nếu có).
5. Tab **Sản phẩm / giá NCC**: thêm dòng
   - Mẫu sản phẩm
   - Đơn giá thuê NCC / tháng (nhóm Quản lý)
   - Tháng tối thiểu NCC (nếu có)
6. Bấm **Kích hoạt**.

Có thể tạo HĐ từ form partner → tab **Hợp đồng với NCC** (NCC đã điền sẵn).

### Bước 3.2 — Lưu ý quan trọng

- **Không đổi Chế độ quản lý** sau khi đã nhận hàng hoặc đã tạo lô.
- Mỗi HĐ chỉ dùng **một** chế độ trong suốt vòng đời.

### So sánh nhanh 3 chế độ

| Chế độ | Hàng vào đâu? | Cho thuê công trình | Theo dõi |
|---|---|---|---|
| **Đơn giản** | Kho tự có (WH/Stock) | Như bình thường (không chọn lô) | SL đang thuê NCC + tiền/tháng |
| **Truy xuất lô** | Kho thuê ngoài (tách) | VC phải chọn nguồn Thuê ngoài + lô | Sổ lô / ledger |
| **Giao thẳng** | Không qua kho (hoặc chỉ tạo lô sẵn) | VC dropship NCC → công trình | Sổ lô |

---

## 4. Luồng Đơn giản (khuyến nghị mặc định)

Dùng khi: thiếu hàng → thuê NCC về **kho mình** → cho thuê công trình như hàng thường → trả NCC khi còn tồn dư.

```text
NCC ──nhận──► Kho mình ──VC khách──► Công trình
                ▲                        │
                └──── khách trả ─────────┘
                │
                └──trả NCC (khi còn tồn dư)──► NCC
```

### 4.1. Nhận hàng từ NCC

**Cách ưu tiên:** mở HĐ thuê ngoài (đã **Kích hoạt**) → tab **Nhập / Trả NCC** → thêm dòng trong **Nhận từ NCC** → mở phiếu → **Xác nhận nhận hàng**.

Hoặc menu: **Thuê ngoài → Nhận từ NCC → New** (vẫn dùng được).

1. Chọn HĐ thuê ngoài (đang hiệu lực, chế độ Đơn giản) — đã điền sẵn nếu tạo từ tab HĐ.
2. Ngày nhận; **Cách nhập** = Về kho.
3. Thêm dòng: sản phẩm (biến thể) + số lượng — sản phẩm phải thuộc mẫu đã khai trên HĐ.
4. Bấm **Xác nhận nhận hàng**.

Hệ thống sẽ:

- Nhập kho **tồn kho công ty** (không tạo lô thuê ngoài).
- Tăng trên dòng HĐ: **SL đã nhận**, **SL đang thuê NCC**.

Kiểm tra: mở lại HĐ → cột **SL đang thuê NCC** / **Tiền/tháng ước tính**.

### 4.2. Cho thuê công trình

Thao tác **như hợp đồng thuê khách bình thường**:

1. HĐ khách → tạo phiếu vận chuyển **Giao hàng**.
2. **Nguồn hàng** để **Tự có** (không cần chọn lô).
3. Tạo / xác nhận phiếu kho như cũ.

**SL đang thuê NCC không giảm** khi giao khách — vì bạn vẫn đang “nợ” NCC cho đến khi trả NCC.

### 4.3. Khách trả hàng

VC loại **Trả hàng**, nguồn **Tự có** — hàng về kho mình như luồng rental cũ.

### 4.4. Trả NCC (khi còn hàng dư trong kho)

**Cách ưu tiên:** HĐ → tab **Nhập / Trả NCC** → **Trả NCC**. Menu **Thuê ngoài → Trả NCC** vẫn dùng được.

1. Chọn đúng HĐ (chế độ Đơn giản) — đã điền sẵn nếu tạo từ tab HĐ.
2. Dòng trả: chọn **Sản phẩm** + số lượng (không bắt buộc lô).
3. **Xác nhận trả NCC**.

Điều kiện hệ thống kiểm tra:

- Số lượng ≤ **SL đang thuê NCC** còn lại trên HĐ.
- Số lượng ≤ **tồn thực tế** tại kho tự có (còn dư mới trả được).

Sau khi xác nhận: **SL đã trả** tăng, **SL đang thuê** giảm; tồn kho xuất về NCC.

### 4.5. Xem tiền phải trả NCC hàng tháng

*(Nhóm Quản lý)*

1. **Thuê ngoài → Công nợ thuê NCC**
2. Chọn công ty / HĐ (tuỳ chọn) + khoảng ngày.
3. Bấm **Tính**.

Công thức MVP: `SL đang thuê NCC × đơn giá / tháng` trên từng dòng HĐ.

---

## 5. Luồng Truy xuất lô + kho thuê ngoài

Dùng khi: cần biết **lô nào** đang ở kho tạm / công trình / đã trả NCC; không trộn với kho tự có.

```text
NCC ──nhận──► Kho thuê ngoài ──VC (nguồn Thuê ngoài + lô)──► Công trình
                    ▲                                         │
                    └──────── khách trả (cùng lô) ────────────┘
                    │
                    └── Trả NCC (từ kho TN, không còn ở CT) ──► NCC
```

### 5.1. Tạo HĐ

Chế độ quản lý = **Truy xuất lô + kho thuê ngoài** → Kích hoạt.

### 5.2. Nhận từ NCC

1. **Nhận từ NCC** → chọn HĐ tracked.
2. Cách nhập = **Về kho**.
3. Xác nhận → tạo **lô** (mã kiểu `TN/xxxxx`), nhập **Kho thuê ngoài**, ghi sổ cái.

Xem lô: **Thuê ngoài → Sổ lô** hoặc nút **Lô** trên form HĐ.

Trên sổ lô xem các **xô số lượng**:

- SL tại kho thuê ngoài  
- SL đang ở công trình  
- SL đã trả NCC / hỏng  

### 5.3. Giao khách (bắt buộc gắn lô)

1. Trên HĐ **khách**, tạo VC **Giao hàng**.
2. Đặt **Nguồn hàng = Thuê ngoài**.
3. Mỗi dòng sản phẩm: chọn **Lô thuê ngoài** còn SL tại kho TN (cùng sản phẩm).
4. **Một phiếu VC chỉ một nguồn** — không trộn Tự có + Thuê ngoài trên cùng phiếu (tách 2 phiếu nếu cần).
5. Tạo / xác nhận phiếu kho.

Hàng xuất từ **Kho thuê ngoài → khách**. Sổ lô: kho TN giảm, công trình tăng.

### 5.4. Khách trả

1. VC **Trả hàng**, **Nguồn hàng = Thuê ngoài**.
2. Chọn đúng **lô** đang còn SL ở công trình.
3. Xác nhận → hàng về **Kho thuê ngoài** (không về kho tự có).

### 5.5. Trả NCC

1. **Trả NCC** → chọn HĐ tracked.
2. Mỗi dòng chọn **Lô** + SL (lô phải còn tại kho TN, **không** còn ở công trình).
3. Xác nhận → xuất kho TN về NCC, đóng lô khi hết.

Nếu còn hàng ở công trình mà bấm trả NCC → hệ thống **chặn** (phải thu khách trước).

---

## 6. Luồng Giao thẳng công trình

Dùng khi: NCC giao thẳng công trình, không (hoặc ít) qua kho mình.

### 6.1. Chuẩn bị lô

Cách A — **Thuê ngoài → Tạo lô giao thẳng** (wizard):

1. Chọn HĐ (nên dùng chế độ **Giao thẳng công trình**).
2. Sản phẩm + SL + ngày → **Tạo lô giao thẳng**.

Cách B — **Nhận từ NCC** trên HĐ pass_through với cách nhập chuẩn bị giao thẳng (tạo lô, không nhập kho TN).

### 6.2. Giao / trả trên VC khách

1. VC **Giao hàng**, nguồn **Thuê ngoài**, chọn lô giao thẳng.
2. Phiếu kho: NCC → khách (dropship).
3. Khi trả: VC trả, nguồn Thuê ngoài, chọn lô → khách → NCC.

**Không** dùng phiếu **Trả NCC** kiểu kho dư cho chế độ này (hệ thống báo dùng VC trả).

---

## 7. Các menu hỗ trợ khác

### 7.1. Tình trạng SP

**Thuê ngoài → Tình trạng SP**

- KPI / nút mở nhanh: kho TN, đang công trình, idle, đến hạn trả NCC.
- Bấm **Làm mới** sau khi có phát sinh.

*(Chủ yếu hữu ích với chế độ có lô / kho TN.)*

### 7.2. Panel thiếu hàng

**Thuê ngoài → Panel thiếu hàng**

1. Chọn sản phẩm + SL cần giao.
2. **Tính** → xem: tồn tự có | kho thuê ngoài | tổng sẵn sàng | thiếu.
3. Nếu thiếu → gợi ý nhận NCC hoặc giao thẳng.

### 7.3. Báo cáo margin *(Quản lý)*

So sánh doanh thu thuê khách (dòng gắn lô) với chi phí possession NCC — dùng cho chế độ truy xuất lô / phân tích sâu.

### 7.4. Đối soát kho TN *(Quản lý)*

So sánh tồn **Kho thuê ngoài** với tổng SL theo sổ lô. Nếu lệch (vd. điều chỉnh kho tay) → xử lý thủ công.

---

## 8. Checklist thao tác thường ngày (Đơn giản)

1. [ ] NCC đã tick **NCC thuê ngoài**
2. [ ] HĐ thuê ngoài **Đơn giản** đã **Kích hoạt**, có dòng giá
3. [ ] **Nhận từ NCC** khi hàng về kho
4. [ ] Cho thuê CT bằng HĐ khách + VC **Tự có** như bình thường
5. [ ] Khi còn tồn dư và muốn trả NCC → **Trả NCC** (đủ `qty_open` + đủ tồn)
6. [ ] Cuối tháng: Quản lý mở **Công nợ thuê NCC** → Tính

---

## 9. Lỗi thường gặp

| Hiện tượng | Nguyên nhân / cách xử lý |
|---|---|
| Không thấy menu Thuê ngoài | Thiếu group Nhân viên thuê ngoài; refresh session |
| Không chọn được NCC | Partner chưa bật **NCC thuê ngoài** |
| Không kích hoạt HĐ | Chưa có dòng sản phẩm |
| Không đổi được chế độ quản lý | Đã nhận hàng / đã có lô — đúng thiết kế |
| Trả NCC bị chặn (simple) | Vượt SL đang thuê hoặc tồn kho không đủ |
| Trả NCC bị chặn (tracked) | Còn SL ở công trình hoặc chưa chọn lô |
| VC Thuê ngoài không tạo được phiếu kho | Thiếu lô trên dòng, hoặc trộn hai kiểu lô trên một phiếu |
| Sản phẩm không có trên HĐ | Thêm dòng mẫu SP trên HĐ NCC trước khi nhận |

---

## 10. Thuật ngữ nhanh

| Thuật ngữ UI | Ý nghĩa |
|---|---|
| HĐ thuê ngoài | Hợp đồng với NCC (bạn là bên thuê) |
| SL đang thuê NCC | Số lượng còn “nợ” NCC (= nhận − trả), chế độ Đơn giản |
| Kho thuê ngoài | Kho nội bộ tách, chỉ dùng chế độ Truy xuất lô |
| Lô (TN/…) | Một lần nhận / chuẩn bị giao thẳng, theo dõi vị trí chi tiết |
| Nguồn hàng (VC) | Tự có hoặc Thuê ngoài — một phiếu một nguồn |
| Công nợ thuê NCC | Ước tính tiền thuê phải trả NCC theo tháng |

---

## Tham chiếu kỹ thuật

- ADR: [`DECISIONS.md`](DECISIONS.md) (DEC-S07 policy registry, DEC-S08 obligation vs lot)
- Worklog: [`WORKLOG.md`](WORKLOG.md)
