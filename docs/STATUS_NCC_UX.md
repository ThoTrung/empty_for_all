# Hiện trạng UX NCC — tạm dừng (2026-08-01)

Đọc file này khi quyết định bước tiếp. Chi tiết ADR: [DECISIONS.md](DECISIONS.md). Hướng dẫn NV: [USER_GUIDE.md](USER_GUIDE.md).

## Đã ship (A1 + B1)

| Phase | Nội dung | Version | DEC | Test tag |
|---|---|---|---|---|
| 0 | Partner: tab HĐ thuê ↔ `is_rental_customer`; tab HĐ với NCC ↔ `is_rental_supplier` + O2M | `rental` 17.0.1.0.81 · `rental_subrent` 17.0.1.0.5 | DEC-S10 | `subrent_partner_tabs` |
| 1 | Form HĐ NCC: ngày/số giấy, đại diện NCC/ta, notebook Thông tin + SP/giá | `rental_subrent` 17.0.1.0.6 | DEC-S11 | `subrent_contract_form` |
| 2 | Tab **Nhập / Trả NCC** embed `receipt_ids` / `return_ids`; menu list giữ create | `rental_subrent` 17.0.1.0.7 | DEC-S12 | `subrent_contract_moves` |

**Không đổi (cố ý):** model tách `rental.contract` vs `rental.subrent.contract`; policy/stock `simple`; không hóa đơn NCC; không unify sang `rr.transport`.

**Multi-role partner (trước đó):** `is_rental_customer` + `is_rental_supplier` trên `rental` · DEC-29 / DEC-S09 · `rental` ~17.0.1.0.78–80.

### File chính

- Partner tabs: `rental/views/res_partner_view.xml`, `rental_subrent/models/res_partner.py`, `rental_subrent/views/res_partner_view.xml`
- Form HĐ: `rental_subrent/models/rental_subrent_contract.py`, `views/rental_subrent_contract_view.xml`
- Nhận/Trả (model cũ): `rental_subrent/models/rental_subrent_receipt.py`, `rental_subrent_return.py` + views/menu

### Smoke UI

1. Partner chỉ NCC → chỉ tab **Hợp đồng với NCC**; tick thêm Khách thuê → cả hai tab.
2. Từ tab NCC tạo HĐ (default **Đơn giản**) → điền meta/đại diện/dòng giá → Kích hoạt.
3. Tab **Nhập / Trả NCC** → nhận → `qty_open` tăng; trả → giảm. Menu **Nhận/Trả** vẫn mở được.

```bash
# Docker (ví dụ)
odoo -d rental -u rental,rental_subrent --test-enable --stop-after-init \
  --test-tags=subrent_partner_tabs,subrent_contract_form,subrent_contract_moves,partner_multi_role
```

---

## Backlog — chờ quyết định

Thứ tự gợi ý không bắt buộc; mỗi mục độc lập về phạm vi.

1. **Ẩn create trên menu Nhận/Trả** — chỉ list; tạo primary từ tab HĐ (nhỏ, ít rủi ro).
2. **UI tracked / pass_through** — làm giàu form/luồng 2 chế độ còn lại (chưa đụng Phase 0–2).
3. **Unify Nhận/Trả → `rr.transport`** — refactor lớn; thay / bọc `rental.subrent.receipt|return`.
4. **Hóa đơn / `account.move` công nợ NCC** — ngoài wizard Công nợ hiện tại.
5. **Giá NCC↔NCC** — [DEBT-05](../../rental/docs/BUG_LOG.md) trên HĐ khách khi partner vừa NCC vừa KH.
6. **Rename `customer_type`** — [DEBT-04](../../rental/docs/BUG_LOG.md) (`rental_partner_kind` / `partner_form_mode`).

Khi chọn hướng: cập nhật DEC mới + bump version module tương ứng; giữ nguyên nguyên tắc *additive* trừ khi DEC nói rõ phá tương thích.
