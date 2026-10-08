# Decisions (ADR) — rental_subrent

- DEC-S01 — Ledger bất biến (`rental.subrent.ledger`); qty lô computed · `models/rental_subrent_lot.py`
- DEC-S02 — Một `rr.transport` một `source_type` (owned|subrent); cấm mixed · `models/rr_transport.py`
- DEC-S03 — Return/compensation subrent bắt buộc `subrent_lot_id`; picking dest WH/Subrent hoặc Supplier · `_rental_picking_locations`
- DEC-S04 — Billing khách giữ DEC-17; không gắn location vào HSTT
- DEC-S05 — Cost possession = calendar days; revenue = helper ngày thuê khách
- DEC-S06 — Into_stock tracked → location `is_rental_subrent_stock`; pass_through = dropship
- DEC-S07 — Policy registry (`services/subrent_policies/`): `simple` | `tracked` | `pass_through`; receipt/return/transport dispatch qua `contract.get_subrent_policy()`
- DEC-S08 — Hai sổ: Obligation (`qty_*` trên contract.line, policy simple) vs Lot ledger (tracked/pass_through)
- DEC-S09 — NCC dùng `is_rental_supplier` định nghĩa trên `rental` (multi-role với `is_rental_customer`); không còn field riêng module · DEC-29
- DEC-S10 — Form partner: tab «Hợp đồng thuê» chỉ khi `is_rental_customer`; tab «Hợp đồng với NCC» (`subrent_contract_ids`) chỉ khi `is_rental_supplier`; tạo HĐ từ tab (default `simple`). Không gộp model với `rental.contract` · Phase 0 UX
- DEC-S11 — HĐ NCC form B1: `contract_date`/`contract_number` + đại diện NCC/bên ta (optional); notebook Thông tin + SP/giá · Phase 1
- DEC-S12 — Embed Nhận/Trả trên HĐ (`receipt_ids`/`return_ids`, tab «Nhập / Trả NCC»); menu list giữ create; không unify `rr.transport` · Phase 2 A1
- Hook core: `rr.transport._rental_picking_locations()` trong module `rental`

## Open / backlog (sau A1+B1 — xem STATUS_NCC_UX.md)

Tạm dừng 2026-08-01. Chưa DEC:

- Ẩn create menu Nhận/Trả (chỉ list)
- UI tracked / pass_through
- Unify receipt/return → `rr.transport`
- Hóa đơn / AP NCC
- Giá NCC↔NCC (DEBT-05 trên `rental`)
- Rename `customer_type` (DEBT-04 trên `rental`)
