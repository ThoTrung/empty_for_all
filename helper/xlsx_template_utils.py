# -*- coding: utf-8 -*-
"""Shared helpers for rental Excel templates (placeholders, header styles)."""
from copy import copy

from openpyxl.styles import Alignment
from openpyxl.utils import get_column_letter


def replace_placeholders_in_sheet(ws, replacements):
    """Replace {{key}} substrings in all string cells (including merged top-left)."""
    for row in ws.iter_rows():
        for cell in row:
            val = cell.value
            if val is None or not isinstance(val, str):
                continue
            new_val = val
            for key, repl in replacements.items():
                if key in new_val:
                    new_val = new_val.replace(key, str(repl))
            if new_val != val:
                cell.value = new_val


def set_cell_wrap_text(cell, wrap=True, vertical="center", horizontal="center"):
    if cell.alignment:
        al = copy(cell.alignment)
        al.wrapText = wrap
        if vertical:
            al.vertical = vertical
        if horizontal:
            al.horizontal = horizontal
        cell.alignment = al
    else:
        cell.alignment = Alignment(
            wrap_text=wrap,
            vertical=vertical,
            horizontal=horizontal,
        )


def clone_cell_style(ws, src_row, src_col, dst_row, dst_col, wrap_text=False):
    src = ws.cell(src_row, src_col)
    dst = ws.cell(dst_row, dst_col)
    if src.has_style:
        dst.font = copy(src.font)
        dst.border = copy(src.border)
        dst.fill = copy(src.fill)
        dst.number_format = copy(src.number_format)
        dst.protection = copy(src.protection)
        dst.alignment = copy(src.alignment)
    if wrap_text:
        set_cell_wrap_text(dst, wrap=True)


def apply_product_column_styles(
    ws,
    start_col,
    last_col,
    header_rows,
    ref_col,
    data_start_row=None,
    data_end_row=None,
    total_row=None,
    header_wrap=True,
):
    """
    Copy styles from ref_col onto every product column (D..last), including
    columns inside the template width that were overwritten when building headers.
    """
    if last_col < start_col:
        return
    for col in range(start_col, last_col + 1):
        for row in header_rows:
            clone_cell_style(
                ws, row, ref_col, row, col, wrap_text=header_wrap
            )
        if data_start_row is not None and data_end_row is not None:
            for row in range(data_start_row, data_end_row + 1):
                clone_cell_style(ws, data_start_row, ref_col, row, col)
        if total_row:
            clone_cell_style(ws, total_row, ref_col, total_row, col)


def find_transport_matrix_layout(ws, default=(14, 15, 16, 17)):
    """Return (title_row, group_header_row, variant_header_row, data_start_row)."""
    for row in ws.iter_rows(min_row=1, max_row=40):
        for cell in row:
            val = cell.value
            if isinstance(val, str) and "Chủng loại" in val:
                title_row = cell.row
                return title_row, title_row + 1, title_row + 2, title_row + 3
    return default


def unmerge_row_span(ws, row, min_col, max_col):
    """Remove horizontal merges on a row between min_col and max_col."""
    to_remove = []
    for rng in list(ws.merged_cells.ranges):
        if rng.min_row == rng.max_row == row and rng.min_col >= min_col and rng.max_col <= max_col:
            to_remove.append(str(rng))
        elif rng.min_row == rng.max_row == row and not (rng.max_col < min_col or rng.min_col > max_col):
            to_remove.append(str(rng))
    for ref in to_remove:
        ws.unmerge_cells(ref)
