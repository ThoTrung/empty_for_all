# Bug log

> Active bugs + tech debt. Resolved → xoá khỏi đây.

## Active

_(none)_

## Tech debt

- DEBT-01 — Manifest missing `account`,`mail` → add to `depends` after prod check
- DEBT-02 — `rental.invoice.line` compute uses `write()` → assign fields in compute
- DEBT-03 — Controllers `sudo()` without company check → validate `company_id in env.companies`
- DEBT-04 — Rename `res.partner.customer_type` → `rental_partner_kind` / `partner_form_mode` (DEC-29: field không còn nghĩa «loại khách»; label UI đã là «Kiểu form»)
- DEBT-05 — Giá NCC↔NCC: multi-role cho phép chọn partner vừa NCC vừa KH; chưa có pricelist / `rental_price_class` / rule giá riêng trên `rental.contract` (follow-up DEC-29)
- DEBT-06 — Backlog UX thuê ngoài sau A1+B1 (chưa chọn): ẩn create menu Nhận/Trả; UI tracked/pass_through; unify → `rr.transport`; hóa đơn AP NCC — xem `rental_subrent/docs/STATUS_NCC_UX.md`
- DEBT-07 — `security/ir_rule.xml:283` `rental_res_partner_company_strict_rule` cho `base.group_system` domain `[(1,'=',1)]` → mọi user có group này (không chỉ super-admin) đọc/sửa/xoá `res.partner` xuyên company vĩnh viễn, không chỉ lúc `res.company.create()`. Cần domain hẹp lại đúng case cần exempt.
- DEBT-08 — `views/menu.xml:90` `menu_product_template`/`menu_product_product` đổi parent từ `menu_stock_master` (groups có `rental.group_rental_transport_courier`) sang `menu_danh_muc_root` (chỉ `rental.group_rental_staff`) → group courier-only mất quyền xem menu Vật tư dù item vẫn còn list group courier. Cần thêm `group_rental_staff` implied bởi courier, hoặc thêm courier group vào `menu_danh_muc_root`.
- DEBT-09 — `views/rental_home_dashboard_view.xml:36` load trước `views/menu.xml` trong `__manifest__.py`, nhưng `<function>` gọi `ref()` tới menu id định nghĩa trong `menu.xml` → cài fresh DB (`-i rental`) crash `ValueError: External ID not found`; chỉ ẩn khi `-u` trên DB đã có sẵn id cũ. Cần đổi thứ tự load trong manifest.
- DEBT-10 — `models/transport.py:364` `export_data()` chỉ cộng tổng cột tên đúng `fee`, field mới `fee_actual` (đã có footer sum trong `views/transport_view.xml`) không được cộng tổng khi xuất Excel.
- DEBT-11 — `views/rental_home_dashboard_view.xml:12` function set home action cho `res.users` không có `noupdate` → chạy lại mỗi lần `-u rental`, ghi đè Preferences > Action của user đã tự đổi tay về action cũ.
- DEBT-12 — `models/rental_contract.py:1554` `_get_or_create_hstt_total_product` search-rồi-create không khoá/constraint unique → 2 request đồng thời lúc chưa có product "Tổng thanh toán" nào (lần đầu của 1 company) có thể cùng tạo trùng. Cân nhắc `SELECT ... FOR UPDATE` hoặc unique constraint theo `(name, company_id)`.
- DEBT-13 — `views/product_attribute_view.xml:21` `action_rental_product_attribute` lọc "đã ẩn" bằng domain `name not ilike 'không dùng'` thay vì field `active` → attribute đặt tên trùng chuỗi này bị ẩn nhầm, và đổi label dịch sẽ làm domain hỏng.
- DEBT-14 — `views/menu.xml:29` menu tree cũ (nhiều item set `active="False"`) và mảng `TILES` mới trong `static/src/home_dashboard/home_dashboard.js` cùng mã hoá navigation, không có nguồn sự thật duy nhất → dễ lệch nhau (vd `menu_construction_work`/`menu_construction_address` đã có icon riêng nhưng chưa vào TILES).
- DEBT-15 — `views/rental_home_dashboard_view.xml:35` 4 block `<function model="ir.ui.menu" name="write" context="{'lang': 'vi_VN'}">` copy-paste giống hệt nhau cho 4 menu id khác nhau → nên gộp thành 1 vòng lặp/parametrize, tránh lỗi im lặng khi copy sai `ref()`.

**New bug:** 1 dòng vào Active hoặc Tech debt; resolved → xoá.
