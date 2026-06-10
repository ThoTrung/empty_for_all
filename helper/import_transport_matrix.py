# -*- coding: utf-8 -*-
"""Parse transport-matrix Excel (inverse of export) into rr.transport payloads."""
import re
from collections import OrderedDict
from datetime import date, datetime
from io import BytesIO

from openpyxl import Workbook, load_workbook
from openpyxl.utils import get_column_letter

from odoo import _, fields

from .xlsx_template_utils import find_transport_matrix_layout, replace_placeholders_in_sheet

_SKIP_ROW_MARKERS = ("tồn đầu kỳ", "tổng kl cuối", "tổng kl")
_MD_HEADER = "tổng md"
_DATE_COL = 2
_PLATE_COL = 3
_PRODUCT_START_COL = 4


def _normalize_text(value):
    if value is None:
        return ""
    return str(value).strip()


def _normalize_key(value):
    return _normalize_text(value).casefold()


def _normalize_variant_token(value):
    text = _normalize_text(value)
    if not text:
        return ""
    text = text.casefold()
    text = re.sub(r"\s*m\b", "", text)
    return text.replace(",", ".")


def _parse_excel_date(value):
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = _normalize_text(value)
    if not text:
        return None
    for fmt in ("%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    try:
        return fields.Date.from_string(text)
    except (ValueError, TypeError):
        return None


def _parse_qty(value):
    if value is None or value == "":
        return None
    try:
        qty = float(value)
    except (TypeError, ValueError):
        return None
    if abs(qty) < 1e-12:
        return None
    return int(round(qty))


def _cell_value(ws, row, col):
    return ws.cell(row, col).value


def _merged_top_left_value(ws, row, col):
    """Return the value stored on the merged range top-left for (row, col)."""
    for rng in ws.merged_cells.ranges:
        if rng.min_row <= row <= rng.max_row and rng.min_col <= col <= rng.max_col:
            return ws.cell(rng.min_row, rng.min_col).value
    return _cell_value(ws, row, col)


def _walk_left_value(ws, row, col, min_col=1):
    """For horizontally merged headers, walk left until a value is found."""
    for c in range(col, min_col - 1, -1):
        val = _merged_top_left_value(ws, row, c)
        if val is not None and str(val).strip():
            return val
    return None


def _is_skip_row_label(value):
    key = _normalize_key(value)
    return any(marker in key for marker in _SKIP_ROW_MARKERS)


def _normalize_md_header():
    return _MD_HEADER


def _excel_label(group_name, variant_label=None):
    group = _normalize_text(group_name)
    variant = _normalize_text(variant_label)
    if variant and _normalize_key(variant) != _MD_HEADER:
        return f"{group} - {variant}"
    return group


class TransportMatrixProductResolver:
    """Resolve Excel column labels to product.product records by name."""

    def __init__(self, env, contract=None):
        self.env = env
        self.contract = contract
        self._by_display_name = {}
        self._by_template_name = {}
        self._all_template_names = []
        self._errors = {}

    def _index_products(self):
        if self._by_display_name:
            return
        Product = self.env["product.product"].sudo()
        Template = self.env["product.template"].sudo()
        for product in Product.search([("active", "in", [True, False])]):
            self._by_display_name[_normalize_key(product.display_name)] = product
            self._by_display_name[_normalize_key(product.name)] = product
        for tmpl in Template.search([("active", "in", [True, False])]):
            key = _normalize_key(tmpl.name)
            self._by_template_name.setdefault(key, tmpl)
            self._all_template_names.append(tmpl.name)

    def _similar_template_names(self, group_name, limit=5):
        self._index_products()
        needle = _normalize_key(group_name)
        if not needle:
            return []
        scored = []
        for name in self._all_template_names:
            key = _normalize_key(name)
            if needle in key or key in needle:
                scored.append((0, name))
            elif needle[:4] and needle[:4] in key:
                scored.append((1, name))
        scored.sort(key=lambda item: (item[0], item[1].casefold()))
        return [name for _score, name in scored[:limit]]

    def _contract_product_names(self):
        if not self.contract:
            return []
        names = []
        for line in self.contract.rental_contract_line_ids:
            tmpl = line.product_tmpl_id
            if not tmpl:
                continue
            if len(tmpl.product_variant_ids) <= 1:
                names.append(tmpl.display_name)
            else:
                names.extend(tmpl.product_variant_ids.mapped("display_name"))
        return names

    def _format_resolution_error(self, group_name, variant_label=None, col_letter=None):
        group = _normalize_text(group_name)
        variant = _normalize_text(variant_label)
        excel_label = _excel_label(group, variant)
        parts = [
            _("Tên trên Excel: «%(label)s»") % {"label": excel_label},
        ]
        if col_letter:
            parts.append(_("Cột Excel: %(col)s (header dòng 15–16)") % {"col": col_letter})

        tmpl = self._by_template_name.get(_normalize_key(group))
        if tmpl:
            variant_names = tmpl.product_variant_ids.mapped("display_name")
            if variant:
                parts.append(
                    _("Đã tìm thấy mẫu SP «%(tmpl)s» nhưng không khớp biến thể «%(variant)s».") % {
                        "tmpl": tmpl.display_name,
                        "variant": variant,
                    }
                )
            else:
                parts.append(
                    _("Đã tìm thấy mẫu SP «%(tmpl)s» nhưng không xác định được biến thể.") % {
                        "tmpl": tmpl.display_name,
                    }
                )
            if variant_names:
                parts.append(
                    _("Tên biến thể đúng trong Odoo: %(names)s") % {
                        "names": "; ".join(variant_names),
                    }
                )
        else:
            parts.append(
                _("Không tìm thấy mẫu SP «%(name)s» trong Odoo.") % {"name": group or excel_label}
            )
            similar = self._similar_template_names(group)
            if similar:
                parts.append(
                    _("Gợi ý mẫu SP gần giống: %(names)s") % {"names": "; ".join(similar)}
                )
            contract_names = self._contract_product_names()
            if contract_names:
                parts.append(
                    _("Sản phẩm trên hợp đồng này: %(names)s") % {
                        "names": "; ".join(contract_names),
                    }
                )

        parts.append(
            _("Hãy sửa tên ở header Excel (dòng 15–16) cho khớp một tên trong Odoo ở trên.")
        )
        return "\n".join(parts)

    def resolve(self, group_name, variant_label=None, col_index=None):
        self._index_products()
        group = _normalize_text(group_name)
        variant = _normalize_text(variant_label)
        cache_key = (group, variant, col_index)
        if cache_key in self._errors:
            return None, self._errors[cache_key]

        col_letter = get_column_letter(col_index) if col_index else None
        candidates = []
        if variant and _normalize_key(variant) != _normalize_md_header():
            candidates.append(f"{group} - {variant}")
            candidates.append(f"{group} ({variant})")
        candidates.append(group)

        for label in candidates:
            product = self._by_display_name.get(_normalize_key(label))
            if product:
                return product, None

        tmpl = self._by_template_name.get(_normalize_key(group))
        if tmpl:
            variants = tmpl.product_variant_ids
            if not variant and len(variants) == 1:
                return variants[0], None
            if variant:
                token = _normalize_variant_token(variant)
                for prod in variants:
                    if _normalize_key(prod.display_name) == _normalize_key(f"{group} - {variant}"):
                        return prod, None
                    ptav_names = prod.product_template_variant_value_ids.mapped("name")
                    for name in ptav_names:
                        if _normalize_variant_token(name) == token:
                            return prod, None
                    if token and token in _normalize_variant_token(prod.display_name):
                        return prod, None
                if len(variants) == 1:
                    return variants[0], None

        msg = self._format_resolution_error(group, variant, col_letter=col_letter)
        self._errors[cache_key] = msg
        return None, msg


def _build_column_map(ws, header_second_row, header_third_row):
    """Map 1-based column index -> (group_name, variant_label, column_label)."""
    max_col = ws.max_column or _PRODUCT_START_COL
    columns = {}
    for col in range(_PRODUCT_START_COL, max_col + 1):
        group_name = _walk_left_value(ws, header_second_row, col, min_col=_PRODUCT_START_COL)
        variant_label = _cell_value(ws, header_third_row, col)
        group_text = _normalize_text(group_name)
        variant_text = _normalize_text(variant_label)

        if not group_text and not variant_text:
            continue
        if _normalize_key(variant_text) == _MD_HEADER or _normalize_key(group_text) == _MD_HEADER:
            continue

        if variant_text and _normalize_key(variant_text) == _normalize_key(group_text):
            variant_text = ""

        label = _excel_label(group_text, variant_text)
        columns[col] = {
            "group_name": group_text,
            "variant_label": variant_text,
            "label": label,
            "col_letter": get_column_letter(col),
        }
    return columns


def _contract_product_groups(contract, env):
    """Build product groups from contract quotation lines (template + variants)."""
    from odoo.addons.rental.models import rental_transport_matrix as rtm

    product_tmpls = OrderedDict()
    for line in contract.rental_contract_line_ids:
        tmpl = line.product_tmpl_id
        if not tmpl:
            continue
        entry = product_tmpls.get(tmpl.id)
        if not entry:
            entry = {
                "product_tmpl_id": tmpl.id,
                "product_tmpl_name": tmpl.display_name,
                "products": OrderedDict(),
            }
            product_tmpls[tmpl.id] = entry
        for product in tmpl.product_variant_ids:
            entry["products"][product.id] = {
                "id": product.id,
                "name": product.display_name,
                "variant_name": product.product_template_variant_value_ids.mapped("name")[:1] or "",
            }

    groups = []
    for tmpl_id, p_tmpl in product_tmpls.items():
        p_tmpl["products"] = rtm._sort_products_odict(OrderedDict(p_tmpl["products"]))
        prod_order = list(p_tmpl["products"].keys())
        prods = p_tmpl["products"]
        needs_md = rtm._group_needs_md_column(env, prods, prod_order)
        groups.append({
            "tmpl_id": tmpl_id,
            "p_tmpl": p_tmpl,
            "prod_order": prod_order,
            "needs_md": needs_md,
        })
    return groups


def build_import_template_bytes(contract, env):
    """Generate an empty import template for a rental contract."""
    try:
        data, _source = env["rental.template"].sudo().get_template_bytes(
            contract.company_id,
            "transport_matrix_xlsx",
        )
        wb = load_workbook(BytesIO(data))
        ws = wb.active
        replacements = {
            "{{b_company}}": contract.b_party.parent_id.name or "",
            "{{b_address}}": contract.b_address or "",
            "{{b_representative}}": contract.b_name or "",
            "{{b_function}}": contract.b_function or "",
            "{{a_representative}}": contract.a_name or "",
            "{{a_company}}": contract.a_party.parent_id.name or "",
            "{{a_function}}": contract.a_function or "",
            "{{construction_work_project}}": contract.construction_work_project_id.name or "",
            "{{construction_work_name}}": contract.construction_work_id.name or "",
            "{{construction_work_address}}": contract.construction_work_address or "",
        }
        replace_placeholders_in_sheet(ws, replacements)
        title_row, header_second_row, header_third_row, data_start_row = find_transport_matrix_layout(ws)
    except Exception:
        wb = Workbook()
        ws = wb.active
        title_row, header_second_row, header_third_row, data_start_row = 14, 15, 16, 17
        ws.cell(1, 1).value = "BẢNG TỔNG HỢP KHỐI LƯỢNG THUÊ THIẾT BỊ"
        ws.cell(2, 1).value = f"Dự án: {contract.construction_work_project_id.name or ''}"
        ws.cell(title_row, 4).value = "Chủng loại/ Khối lượng"

    ws.cell(header_second_row - 1, 1).value = "STT"
    ws.cell(header_second_row - 1, 2).value = "Ngày tháng"
    ws.cell(header_second_row - 1, 3).value = "Biển số xe"

    groups = _contract_product_groups(contract, env)
    cur_col = _PRODUCT_START_COL
    for group in groups:
        p_tmpl = group["p_tmpl"]
        if group["needs_md"] and len(group["prod_order"]) > 1:
            span = len(group["prod_order"]) + 1
            ws.merge_cells(
                start_row=header_second_row,
                start_column=cur_col,
                end_row=header_second_row,
                end_column=cur_col + span - 1,
            )
            ws.cell(header_second_row, cur_col).value = p_tmpl["product_tmpl_name"]
            offset = 0
            for prod_id in group["prod_order"]:
                prod = p_tmpl["products"][prod_id]
                label = prod.get("variant_name") or prod.get("name")
                ws.cell(header_third_row, cur_col + offset).value = label
                offset += 1
            ws.cell(header_third_row, cur_col + offset).value = "Tổng MD"
            cur_col += span
        else:
            prod_id = group["prod_order"][0]
            prod = p_tmpl["products"][prod_id]
            ws.merge_cells(
                start_row=header_second_row,
                start_column=cur_col,
                end_row=header_third_row,
                end_column=cur_col,
            )
            ws.cell(header_second_row, cur_col).value = prod["name"]
            cur_col += 1

    ws.cell(data_start_row, 1).value = 1
    ws.cell(data_start_row, 2).value = "dd/mm/yyyy"
    ws.cell(data_start_row, 3).value = "29H-00000"
    ws.cell(data_start_row + 1, 2).value = _(
        "Ghi chú: số lượng dương = xuất (giao), số âm = nhập (trả). Cột C = biển số xe."
    )

    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def parse_transport_matrix_xlsx(file_bytes, env, contract=None):
    """
    Parse an Excel workbook into transport import rows.

    Returns dict with keys: rows, errors, warnings, product_mapping_errors.
    """
    wb = load_workbook(BytesIO(file_bytes), data_only=True)
    ws = wb.active
    _, header_second_row, header_third_row, data_start_row = find_transport_matrix_layout(ws)
    column_map = _build_column_map(ws, header_second_row, header_third_row)
    if not column_map:
        return {
            "rows": [],
            "errors": [_("Không đọc được cột sản phẩm từ file Excel.")],
            "warnings": [],
            "product_mapping_errors": [],
        }

    resolver = TransportMatrixProductResolver(env, contract=contract)
    parsed_rows = []
    global_errors = []
    warnings = []
    product_mapping_errors = []
    seen_product_errors = set()
    seen_keys = {}

    max_row = ws.max_row or data_start_row
    for row_idx in range(data_start_row, max_row + 1):
        date_val = _cell_value(ws, row_idx, _DATE_COL)
        plate_val = _cell_value(ws, row_idx, _PLATE_COL)
        date_text = _normalize_text(date_val)
        if not date_text or _is_skip_row_label(date_text):
            continue
        if date_text.startswith("Ghi chú:"):
            continue

        transport_date = _parse_excel_date(date_val)
        plate = _normalize_text(plate_val)
        row_errors = []
        row_warnings = []

        if not transport_date:
            row_errors.append(_("Dòng %(row)s: không đọc được ngày '%(val)s'.") % {
                "row": row_idx,
                "val": date_val,
            })
        if not plate:
            row_errors.append(_("Dòng %(row)s: thiếu biển số xe (cột C).") % {"row": row_idx})

        lines = []
        has_negative = False
        has_positive = False
        for col, col_info in column_map.items():
            qty = _parse_qty(_cell_value(ws, row_idx, col))
            if qty is None:
                continue
            if qty < 0:
                has_negative = True
            elif qty > 0:
                has_positive = True

            product, err = resolver.resolve(
                col_info["group_name"],
                col_info["variant_label"],
                col_index=col,
            )
            if err:
                detail = _("Dòng %(row)s, cột %(col)s:\n%(detail)s") % {
                    "row": row_idx,
                    "col": col_info["col_letter"],
                    "detail": err,
                }
                row_errors.append(detail)
                err_key = (col_info["col_letter"], col_info["label"])
                if err_key not in seen_product_errors:
                    seen_product_errors.add(err_key)
                    product_mapping_errors.append({
                        "col_letter": col_info["col_letter"],
                        "excel_label": col_info["label"],
                        "detail": err,
                    })
                continue
            lines.append((product.id, abs(qty)))

        if has_negative and has_positive:
            row_errors.append(
                _("Dòng %(row)s: không được trộn số lượng dương (xuất) và âm (nhập) trên cùng một chuyến.") % {
                    "row": row_idx,
                }
            )

        if transport_date and plate:
            dup_key = (transport_date, plate.casefold())
            if dup_key in seen_keys:
                row_errors.append(
                    _("Dòng %(row)s: trùng ngày %(date)s và biển số %(plate)s với dòng %(other)s trong file.") % {
                        "row": row_idx,
                        "date": transport_date,
                        "plate": plate,
                        "other": seen_keys[dup_key],
                    }
                )
            else:
                seen_keys[dup_key] = row_idx

        if not lines and not row_errors:
            warnings.append(_("Dòng %(row)s: không có sản phẩm, bỏ qua.") % {"row": row_idx})
            continue

        transport_type = "return" if has_negative else "delivery"
        parsed_rows.append({
            "row_number": row_idx,
            "transport_date": transport_date,
            "plate": plate,
            "transport_type": transport_type,
            "lines": lines,
            "errors": row_errors,
            "warnings": row_warnings,
        })
        global_errors.extend(row_errors)
        warnings.extend(row_warnings)

    return {
        "rows": parsed_rows,
        "errors": global_errors,
        "warnings": warnings,
        "product_mapping_errors": product_mapping_errors,
    }
