# excel_row_ops.py
from copy import copy
from openpyxl.utils import get_column_letter

from .xlsx_template_utils import apply_product_column_styles, clone_cell_style


def extend_product_column_styles(
    ws,
    start_product_col,
    last_product_col,
    template_last_col,
    header_rows,
    data_start_row,
    data_end_row,
    total_row=None,
    ref_col=None,
):
    """Backward-compatible wrapper — styles all product columns from ref_col."""
    apply_product_column_styles(
        ws,
        start_col=start_product_col,
        last_col=last_product_col,
        header_rows=header_rows,
        ref_col=ref_col or start_product_col,
        data_start_row=data_start_row,
        data_end_row=data_end_row,
        total_row=total_row,
        header_wrap=True,
    )


def _clone_row_styles(ws, src_row, dst_row, min_col=1, max_col=None, copy_values=False):
    """
    Clone row height, cell styles, hyperlinks, comments, and horizontal merges
    from src_row to dst_row. Optionally copy values.
    """
    if max_col is None:
        max_col = ws.max_column

    # Row height/visibility
    if src_row in ws.row_dimensions:
        sdim = ws.row_dimensions[src_row]
        ddim = ws.row_dimensions[dst_row]
        ddim.height = sdim.height
        ddim.hidden = sdim.hidden
        # openpyxl uses 'outlineLevel' (older) or 'outline_level' (newer)
        lvl = getattr(sdim, 'outlineLevel', getattr(sdim, 'outline_level', 0))
        try:
            ddim.outlineLevel = lvl
        except Exception:
            try:
                ddim.outline_level = lvl
            except Exception:
                pass

    # Cell styles (+ values/hyperlinks/comments)
    for col in range(min_col, max_col + 1):
        s = ws.cell(src_row, col)
        d = ws.cell(dst_row, col)

        if s.has_style:
            d.font = copy(s.font)
            d.border = copy(s.border)
            d.fill = copy(s.fill)
            d.number_format = copy(s.number_format)
            d.protection = copy(s.protection)
            d.alignment = copy(s.alignment)

        if copy_values:
            d.value = s.value

        if s.hyperlink:
            d._hyperlink = copy(s.hyperlink)
        if s.comment:
            d.comment = copy(s.comment)

    # Replicate horizontal merges that live on src_row
    for rng in list(ws.merged_cells.ranges):
        if rng.min_row == rng.max_row == src_row:
            ref = f"{get_column_letter(rng.min_col)}{dst_row}:{get_column_letter(rng.max_col)}{dst_row}"
            try:
                ws.merge_cells(ref)
            except ValueError:
                pass


def _shift_tail(ws, start_row, rows_to_shift, min_col=1, max_col=None):
    """
    Move everything from start_row..max_row DOWN (rows_to_shift>0) or UP (rows_to_shift<0)
    without losing formatting below. translate=True adjusts formulas.
    """
    if rows_to_shift == 0:
        return
    if max_col is None:
        max_col = ws.max_column
    if start_row > ws.max_row:
        return

    from_ref = f"{get_column_letter(min_col)}{start_row}:{get_column_letter(max_col)}{ws.max_row}"
    ws.move_range(from_ref, rows=rows_to_shift, cols=0, translate=True)


def insert_rows_above(ws, anchor_row, count, min_col=1, max_col=None, template_row=None, clone_values=False):
    """
    Insert `count` rows ABOVE `anchor_row` and clone styles from `template_row`
    (default: anchor_row) onto each inserted row. Returns the list of new row indices.
    """
    if count <= 0:
        return []

    if max_col is None:
        max_col = ws.max_column
    if template_row is None:
        template_row = anchor_row

    # 1) Push tail down starting at the insertion point
    _shift_tail(ws, start_row=anchor_row, rows_to_shift=count, min_col=min_col, max_col=max_col)

    # 2) Paint the new rows
    inserted = []
    for i in range(count):
        r = anchor_row + i
        inserted.append(r)
        # clear any residual values
        for c in range(min_col, max_col + 1):
            ws.cell(r, c).value = None
        _clone_row_styles(ws, src_row=template_row, dst_row=r,
                          min_col=min_col, max_col=max_col, copy_values=clone_values)
    return inserted


def insert_rows_below(ws, anchor_row, count, min_col=1, max_col=None, template_row=None, clone_values=False):
    """
    Insert `count` rows BELOW `anchor_row` and clone styles from `template_row`
    (default: anchor_row) onto each inserted row. Returns the list of new row indices.
    """
    if count <= 0:
        return []

    if max_col is None:
        max_col = ws.max_column
    if template_row is None:
        template_row = anchor_row

    # 1) Push tail down from the row just below the anchor
    _shift_tail(ws, start_row=anchor_row + 1, rows_to_shift=count, min_col=min_col, max_col=max_col)

    # 2) Paint the new rows (immediately below the anchor)
    inserted = []
    for i in range(1, count + 1):
        r = anchor_row + i
        inserted.append(r)
        for c in range(min_col, max_col + 1):
            ws.cell(r, c).value = None
        _clone_row_styles(ws, src_row=template_row, dst_row=r,
                          min_col=min_col, max_col=max_col, copy_values=clone_values)
    return inserted
