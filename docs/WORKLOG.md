# Worklog (giữ ~3 entry mới; cũ hơn xoá bớt)

## 2026-07-11 — Import mẫu compact (Chủng loại row 3)

files: `helper/import_transport_matrix.py` (`_sheet_has_ghi_chu_above`), `tests/test_transport_import.py`
why: Xác nhận parse layout bỏ header/footer dài vẫn đúng (neo «Chủng loại»); Tải biểu mẫu không ghi Ghi chú vào dòng data khi mẫu đã có note phía trên.
validation: `test_parse_compact_layout_chung_loai_row_3`, `test_build_import_template_keeps_compact_note_out_of_data`.

## 2026-07-11 — Tree product.template: kéo thả theo `order`

files: `views/product_template_view.xml` (handle + `default_order`), `models/product_template.py` (`_order`), `__manifest__.py` 17.0.1.0.35
why: Cho phép kéo thả đổi thứ tự SP trên list; ghi vào field `order` (cùng field dùng khi xuất cột biểu mẫu import).
validation: `-u rental`; mở Products tree, kéo handle — `order` cập nhật, list sort theo `order, id`.

## 2026-07-11 — Mẫu riêng cho Tải biểu mẫu import XNK

files: `models/rental_template.py` (`transport_import_xlsx`), `static/file_template/transport_import_template.xlsx`, `helper/import_transport_matrix.py`, `__manifest__.py` 17.0.1.0.34
why: Tách khung Excel «Tải biểu mẫu» khỏi «Bảng xác nhận khối lượng» để upload header/footer riêng; fallback module copy từ transport_matrix_template.
validation: tạo `rental.template` loại Biểu mẫu import xuất nhập kho (XLSX), đánh dấu Mặc định; `-u rental`.
