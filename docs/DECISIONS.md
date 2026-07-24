# Decisions (ADR)

> Đọc khi sắp đổi kiến trúc.

- DEC-01 — Billing centralized in `rental_contract_services` · `services/rental_contract_services.py`
- DEC-02 — Primary invoice = `account.move` (not `rental.invoice`) · `models/account_move.py`, `wizard/create_invoice_wizard.py`
- DEC-03 — Contract edit lock via `write()` + context bypass · `models/rental_contract.py`
- DEC-04 — Transport done via picking + `sudo` · `models/stock_picking.py`, `models/transport.py`
- DEC-05 — Courier isolated from staff (record rules) · `security/ir_rule.xml`, `views/menu.xml`
- DEC-06 — Matrix model + non-overlap constraint · `models/rental_transport_matrix.py`
- DEC-07 — Multi-company via `mc.group.mixin` · `models/models.py`, `security/ir_rule.xml`
- DEC-08 — Excel import transport (col C=plate, neg qty=return) · `helper/import_transport_matrix.py`, `wizard/rental_transport_import_wizard.py`
- DEC-09 — Mẫu nhiều biến thể mét dài: khớp trả/phạt theo POOL mét dài gộp toàn mẫu (LIFO theo ngày giao), KHÔNG theo từng biến thể · `services/rental_contract_services.py` (`_apply_pooled_returns_by_template`)
- DEC-10 — Phí VC tách kỳ thuê: cutoff `transport_fee_until_date` + đánh dấu `fee_billed_date`/`fee_invoice_id` trên `rr.transport`; HSTT gộp 1 dòng + sheet Chi tiết phí VC · `models/rental_contract.py`, `wizard/create_invoice_wizard.py`
- DEC-11 — `rental.contract.line.price_unit` = đơn giá thuê **theo tháng** (cùng `list_price`); export báo giá: cột tháng = `price_unit`, cột ngày = `/30`; PDF nhãn «/ tháng» · `controllers/rental_contract_controller.py`, `reports/quotation_price_report.xml`
- DEC-12 — `transport_fee_share_min_months` / `prices_include_tax`: điều khoản + placeholders xuất báo giá; **chưa** đổi logic chia phí VC trên hóa đơn · `models/rental_contract.py`
- DEC-13 — HSTT Excel cột ngày thuê: `=MAX(0,C-B[+1]-N)` với `N` = holiday trên cùng khoảng hiệu lực `rental_days_between_with_holiday` (khớp hóa đơn / footer SUM) · `models/rental_contract.py`
- DEC-14 — KLCT dùng số lượng có dấu theo chiều vận chuyển: `delivery = +qty`, `return/compensation = -qty`; `rr.transport.line.qty` vẫn lưu dương. HSTT kết hợp tham chiếu dòng trả riêng cho số lượng âm và cộng toàn bộ chuyển động cùng ngày cho dòng dương đã gộp · `models/rental_transport_matrix.py`, `helper/transport_matrix_export.py`, `models/rental_contract.py`
- DEC-15 — Hóa đơn tổng HSTT cố định VAT bán ra 8%; tự sửa thuế cũ trên sản phẩm dịch vụ theo kỳ và không map qua fiscal position sang 10% · `models/rental_contract.py`
- DEC-16 — HSTT cột F chỉ tham chiếu ô KLCT khi số lượng khớp dòng billing (BOB và trong kỳ); lệch (trả/phạt tách lô) → ghi literal để không tính trùng · `helper/transport_matrix_export.py`, `models/rental_contract.py`
- DEC-17 — SL đang thuê, billing, KLCT/matrix, phí VC và đền bù chỉ lấy `rr.transport` có `state = done`; tra cứu cuối ngày dùng cùng engine LIFO/HSTT, gộp theo `product.template` · `services/rental_contract_services.py`, `helper/transport_matrix_export.py`, `models/rental_transport_matrix.py`, `models/rental_contract.py`, `wizard/rental_rented_qty_wizard.py`
- DEC-18 — HSTT / bảng thanh toán XLSX: dòng bắt đầu ghi data lấy từ `rental.template.data_start_row` (default 13 = layout mẫu module); mỗi công ty tự set (vd. 15) khi file mẫu đổi layout · `models/rental_template.py`, `models/rental_contract.py`
- DEC-19 — Option HĐ `minimum_penalty_current_period_only`: chỉ phạt lô giao trong kỳ thanh toán; BOB/lô trước kỳ trả trong kỳ luôn `returned`. HSTT phần không phạt = layout trừ tiền (full present + credit âm từ ngày trả → cuối kỳ); phần phạt giữ đối ứng/`min_end` · `services/rental_contract_services.py`, `models/rental_contract.py`
- DEC-20 — «Xuất KLCT + HSTT»: download bằng `<a download>` (không `window.open` sau RPC). Dòng credit trả hàng ghi F→KLCT return + G/I công thức giống billing (DEC-16 guard F vẫn áp dụng) · `static/src/js/download_and_close.js`, `models/rental_contract.py`
- DEC-21 — Analytics Hub: Dashboard OWL + widget registry; on-hire fact từ `calc_rented_qty_as_of` (không `stock.quant`); drill-down Graph/List/Pivot. Thêm thống kê sau = thêm provider/widget · `models/rental_analytics_*.py`, `static/src/analytics_dashboard/`
- DEC-22 — Analytics harden: snapshot TTL 15p + unique + cron giữ 14 ngày; KPI on-hire tách theo ĐVT (không cộng lẫn); Dashboard filter KH/công trình + tz user; widget công nợ `account.move.amount_residual` group `rental_partner_company_id` · `models/rental_analytics_*.py`, `models/account_move.py`

**New ADR:** thêm 1 dòng `DEC-NN`.
