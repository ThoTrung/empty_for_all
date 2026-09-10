# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Nạp `product.category.spa_sales_commission_percent` từ % ghi trong TÊN danh mục.

    Bối cảnh: tính năng "Hoa hồng SP" của phiếu lương Spa
    (`spa.staff.payroll._spa_recompute_kpi_and_sales_commission_lines`) chỉ đọc field số
    `product.category.spa_sales_commission_percent`, trong khi dữ liệu hiện tại chỉ ghi tỉ lệ
    vào TÊN danh mục ("LQ 10%", "Dermalogica 7%", "Buổi lẻ 2%"...). Vì field số = 0 cho mọi
    danh mục nên hoa hồng luôn ra rỗng.

    Migration này parse con số dạng `N%` / `N.N%` / `N,N%` đầu tiên trong tên và ghi vào field.

    An toàn:
    - Chỉ ghi khi field đang 0/NULL  -> không đè giá trị đã nhập tay, idempotent khi chạy -u lại.
    - Bỏ qua danh mục gốc id=1 ("All") -> tránh cascade % xuống toàn bộ sản phẩm qua cơ chế
      leo parent trong `_spa_get_sales_commission_percent()`.
    - Danh mục không có % trong tên giữ nguyên 0 (phải nhập tay nếu nghiệp vụ muốn tính HH).
    """
    cr.execute(
        r"""
        UPDATE product_category
        SET spa_sales_commission_percent =
            replace((regexp_match(name, '([0-9]+(?:[.,][0-9]+)?)\s*%'))[1], ',', '.')::numeric
        WHERE name ~ '[0-9]+(?:[.,][0-9]+)?\s*%'
          AND id <> 1
          AND COALESCE(spa_sales_commission_percent, 0) = 0
        """
    )
    _logger.info(
        "spa_staff_payroll: nap %% hoa hong tu ten danh muc -> %s danh muc product.category duoc cap nhat",
        cr.rowcount,
    )
