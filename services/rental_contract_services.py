import calendar
import io
from collections import defaultdict
from datetime import date, timedelta

from dateutil.relativedelta import relativedelta
from docxtpl import DocxTemplate


def render_rental_contract_docx(contract):
    # Load template and render (company upload or module default)
    template_stream = contract.env["rental.template"].get_template_path_or_stream(
        contract.company_id,
        "contract_docx",
    )
    today = date.today()
    doc = DocxTemplate(template_stream)
    context = {
        'contract_code': contract.code,
        'contract_number': contract.contract_number or '',
        'a_company_name': contract.a_party.parent_id.name,
        'a_address': contract.a_address,
        'a_name': contract.a_name,
        'a_title': contract.a_party.title.name,
        'a_function': contract.a_function,
        'a_phone': contract.a_phone,
        'a_bank_account': contract.a_bank_account,
        'a_vat': contract.a_vat,
        'a_fax': contract.a_company_party.fax,
        'a_executor_name': contract.a_executor_name,
        'a_executor_title': contract.a_executor_id.title.name,
        'a_executor_function': contract.a_executor_function,

        'b_company_name': contract.b_party.parent_id.name,
        'b_address': contract.b_address,
        'b_name': contract.b_name,
        'b_title': contract.b_party.title.name,
        'b_function': contract.b_function,
        'b_phone': contract.b_phone,
        'b_bank_account': contract.b_bank_account,
        'b_vat': contract.b_vat,
        'b_fax': contract.b_company_party.fax,
        'b_executor_name': contract.b_executor_name,
        'b_executor_title': contract.b_executor_id.title.name,
        'b_executor_function': contract.b_executor_function,

        'construction_work_name': contract.construction_work_id.name,
        'construction_work_project': contract.construction_work_project_id.name if contract.construction_work_project_id else '',
        'construction_work_address': contract.construction_work_address,
        # today is a datetime.date => use .day/.month/.year
        'date_month_year': f"ngày {today.day} tháng {today.month} năm {today.year}",
    }
    idx = 1
    lines = []
    for line in contract.rental_contract_line_ids:
        # context[f'product_name_{idx}'] = line.product_tmpl_id.display_name
        # context[f'uom_{idx}'] = line.uom_id.name
        # # context[f'qty_{idx}'] = 1
        # context[f'price_unit_{idx}'] = line.price_unit
        # context[f'compensation_price_{idx}'] = line.compensation_price

        lines.append({
            'idx': idx,
            'product_name': line.product_tmpl_id.display_name,
            'uom': line.uom_id.name,
            'price_unit': "{:,.0f}".format(line.price_unit).replace(",", ".") if line.price_unit else '',
            'compensation_price': "{:,.0f}".format(line.compensation_price).replace(",",
                                                                                    ".") if line.compensation_price else '',
        })
        idx += 1
    context['lines'] = lines
    # pprint.pprint(context)
    doc.render(context)

    return doc


def contract_line_ratios_by_template(contract, as_of_date=None):
    """Giá dòng HĐ / list_price mẫu — dùng để quy đổi giá kho khi khác báo giá.

    as_of_date: nếu truyền vào, dùng đơn giá có hiệu lực tại ngày đó (TH1 — giá đổi
    theo thời gian). Mặc định dùng đơn giá gốc của dòng báo giá.
    """
    ratios = {}
    for rc_line in contract.rental_contract_line_ids:
        tmpl = rc_line.product_tmpl_id
        lp = tmpl.list_price or 0.0
        price = rc_line._effective_price_unit(as_of_date)
        ratios[tmpl.id] = (price / lp) if lp else 1.0
    return ratios


def month_day_basis(contract, period_end_date):
    """Số ngày dùng để quy giá tháng → giá ngày, theo cấu hình HĐ.

    - "fixed_30": cố định 30 ngày, không phụ thuộc tháng.
    - "calendar" (mặc định): số ngày thực của tháng kỳ thanh toán.
    """
    if contract.monthly_day_basis == "fixed_30":
        return 30
    return calendar.monthrange(period_end_date.year, period_end_date.month)[1]


def unit_price_for_transport_line(contract, product, ratio, period_end_date):
    """Đơn giá theo một ngày thuê (đã nhân ratio báo giá), thống nhất Excel + account.move."""
    tmpl = product.product_tmpl_id
    monthly_eff = product.lst_price * ratio
    dim = month_day_basis(contract, period_end_date)
    if contract.rental_billing_mode == "month":
        return monthly_eff / dim if dim else monthly_eff
    # day mode: giá/ngày trên biến thể (đã nhập trên product.product) × ratio báo giá HĐ
    d = product.rental_price_day or 0.0
    if d:
        return d * ratio
    return monthly_eff / dim if dim else monthly_eff


def monthly_price_for_transport_line(product, ratio):
    """Đơn giá tháng hiệu dụng theo biến thể × tỷ lệ báo giá HĐ."""
    return product.lst_price * ratio


def rental_days_between(start_date, end_date, include_start_day=False):
    """Số ngày thuê giữa 2 mốc; có thể cộng thêm 1 ngày để tính cả ngày bắt đầu."""
    days = (end_date - start_date).days
    if include_start_day:
        days += 1
    return max(days, 0)


def _holiday_days_between(env, company_or_contract, start_date, end_date):
    """Đếm số ngày nghỉ giao nhau (tính theo lịch đã cấu hình, bao gồm 2 đầu mốc).

    Tham số thứ 2 chấp nhận:
    - `rental.contract`: gộp ngày nghỉ toàn hệ thống (theo công ty, không gắn HĐ) + ngày
      nghỉ cấu hình riêng cho hợp đồng đó.
    - `res.company` (tương thích ngược): chỉ lấy ngày nghỉ toàn hệ thống của công ty.
    """
    Holiday = env["rental.holiday"]
    base_domain = [
        ("active", "=", True),
        ("date_from", "<=", end_date),
        ("date_to", ">=", start_date),
    ]
    if getattr(company_or_contract, "_name", None) == "rental.contract":
        contract = company_or_contract
        domain = base_domain + [
            "|",
            ("rental_contract_id", "=", contract.id),
            "&",
            ("rental_contract_id", "=", False),
            ("company_id", "=", contract.company_id.id),
        ]
    else:
        company = company_or_contract
        domain = base_domain + [
            ("rental_contract_id", "=", False),
            ("company_id", "=", company.id),
        ]
    holidays = Holiday.search(domain)
    total = 0
    for holiday in holidays:
        overlap_start = max(start_date, holiday.date_from)
        overlap_end = min(end_date, holiday.date_to)
        if overlap_start <= overlap_end:
            total += (overlap_end - overlap_start).days + 1
    return total


def rental_days_between_with_holiday(env, company_or_contract, start_date, end_date, include_start_day=False):
    """
    Số ngày thuê thực tế sau khi trừ ngày nghỉ.
    - Mặc định: khoảng tính là (start_date, end_date]  => không tính ngày bắt đầu.
    - include_start_day=True: khoảng tính là [start_date, end_date].

    Tham số thứ 2 nhận `rental.contract` (ưu tiên — gộp ngày nghỉ HĐ + toàn hệ thống) hoặc
    `res.company` (tương thích ngược).
    """
    if include_start_day:
        effective_start = start_date
    else:
        effective_start = start_date + timedelta(days=1)
    if effective_start > end_date:
        return 0
    days = rental_days_between(effective_start, end_date, include_start_day=True)
    holiday_days = _holiday_days_between(env, company_or_contract, effective_start, end_date)
    return max(days - holiday_days, 0)


def _minimum_rental_months(contract, product):
    """Kỳ thuê tối thiểu (tháng) áp cho một sản phẩm: ưu tiên ghi đè ở dòng báo giá."""
    tmpl = product.product_tmpl_id
    line = contract.rental_contract_line_ids.filtered(
        lambda l: l.product_tmpl_id == tmpl
    )[:1]
    if line and line.minimum_rental_months:
        return line.minimum_rental_months
    return contract.minimum_rental_months or 0


def _transport_lines_for_billing(env, contract, as_of_date, extra_domain=None):
    """Return official transport lines used by billing and rented-quantity reports.

    Only completed transports are operational facts. Draft or cancelled transports
    must not change invoices, payment tables, or as-of rented quantities.
    """
    domain = [
        ("transport_id", "in", contract.rr_transport_ids.ids),
        ("transport_id.state", "=", "done"),
        ("start_rental_or_return_date", "<=", as_of_date),
    ]
    if extra_domain:
        domain.extend(extra_domain)
    return env["rr.transport.line"].search(
        domain,
        order="start_rental_or_return_date ASC, id ASC",
    )


def _build_billing_events(env, contract, as_of_date):
    """Quy đổi các phiếu xuất/nhập thành các "sự kiện tính tiền" có dấu.

    - Xuất (delivery): sự kiện +billable_qty tại ngày giao, mở một "lô" thuê.
    - Nhập (return): khớp LIFO với các lô đang mở (lô MỚI NHẤT trước). Với mỗi phần
      khớp, ngày kết thúc tính tiền = max(ngày trả thực tế, ngày giao + kỳ tối thiểu)
      → đảm bảo trả sớm vẫn tính đủ kỳ tối thiểu (TH2).
    - Phần chuyển dư (non_billable_qty) không tạo lô, không tính tiền (TH3).

    Trả về list dict: {product, product_id, date, qty(signed)}.
    """
    transport_lines = _transport_lines_for_billing(env, contract, as_of_date)
    open_lots = defaultdict(list)  # product_id -> list of [deliver_date, qty_remaining, min_end]
    events = []
    for line in transport_lines:
        billable = line.billable_qty
        if not billable:
            continue
        product = line.product_id
        pid = product.id
        line_date = line.start_rental_or_return_date
        # Đền bù (mất/hỏng) coi như trả hàng: dừng tính tiền thuê phần đó.
        is_return = line.transport_id.type in ("return", "compensation")
        if not is_return:
            min_months = _minimum_rental_months(contract, product)
            min_end = line_date + relativedelta(months=min_months) if min_months else line_date
            open_lots[pid].append([line_date, billable, min_end])
            events.append({"product": product, "product_id": pid, "date": line_date, "qty": billable})
            continue
        # Return: khớp LIFO
        remaining = billable
        while remaining > 0 and open_lots[pid]:
            lot = open_lots[pid][-1]
            take = min(remaining, lot[1])
            eff_return = max(line_date, lot[2])
            events.append({"product": product, "product_id": pid, "date": eff_return, "qty": -take})
            lot[1] -= take
            remaining -= take
            if lot[1] <= 0:
                open_lots[pid].pop()
        if remaining > 0:
            # Trả nhiều hơn số đang mở (dữ liệu lệch): hạch toán phần dư tại ngày trả thực.
            events.append({"product": product, "product_id": pid, "date": line_date, "qty": -remaining})
    return events


def _build_map_product_and_date_to_line(env, contract, start_date, end_date):
    """Chi tiết theo product.product + ngày bắt đầu (trước khi gộp mẫu cho Excel).

    Điều phối theo cách tính kỳ tối thiểu của hợp đồng:
    - "upfront" (mặc định): tính đủ kỳ tối thiểu ngay tại bảng thanh toán của tháng KH
      trả hàng (front-load) → `_build_map_upfront`.
    - "spread": rải kỳ tối thiểu qua từng tháng (đẩy ngày trả tới hết kỳ) → cách cũ dựa
      trên "sự kiện tính tiền" có dấu.
    """
    if (contract.minimum_rental_billing_mode or "upfront") == "upfront":
        return _build_map_upfront(env, contract, start_date, end_date)
    return _build_map_via_events(env, contract, start_date, end_date)


def _build_billing_line_dict(
    env,
    contract,
    ratios,
    product,
    line_start,
    line_end,
    qty,
    deliver_date,
    start_date,
    end_date,
    kind="present",
    return_date=None,
    min_months=0,
):
    """Dựng một dòng tính tiền (dict) thống nhất cho cả khớp theo biến thể và gộp mét dài.

    - is_bob = giao trước ngày đầu kỳ (mang sang).
    - rental_days: tính cả ngày đầu nếu lô đã/đang chạy từ đầu kỳ (giao <= đầu kỳ).
    - đơn giá lấy theo ngày/tháng + tỷ lệ báo giá HĐ.
    """
    is_bob = deliver_date < start_date
    include_start_day = (
        contract.include_start_day_bob
        if deliver_date <= start_date
        else contract.include_start_day_current
    )
    rental_days = rental_days_between_with_holiday(
        env,
        contract,
        line_start,
        line_end,
        include_start_day=include_start_day,
    )
    tmpl_id = product.product_tmpl_id.id
    ratio = ratios.get(tmpl_id, 1.0)
    unit_price_day = unit_price_for_transport_line(contract, product, ratio, end_date)
    unit_price_month = monthly_price_for_transport_line(product, ratio)
    display_unit_price = (
        unit_price_day if contract.rental_billing_mode == "day" else unit_price_month
    )
    return {
        "start_date": line_start,
        "end_date": line_end,
        "product_name": product.display_name,
        "uom_name": product._get_staff_display_uom().name,
        "qty": qty,
        "rental_days": rental_days,
        "unit_price": unit_price_day,
        "display_unit_price": display_unit_price,
        "total_amount": rental_days * qty * unit_price_day,
        "is_bob": is_bob,
        "include_start_day": bool(include_start_day),
        "kind": kind,
        "deliver_date": deliver_date,
        "return_date": return_date,
        "min_months": min_months,
        "product_id": product.id,
        "tmpl_id": tmpl_id,
    }


def _build_map_upfront(env, contract, start_date, end_date):
    """TH "tính đủ kỳ tối thiểu vào tháng trả hàng".

    Mô phỏng các "lô" thuê theo LIFO (như khi khớp trả hàng) tính đến hết kỳ. Với mỗi
    lô và mỗi kỳ [start_date, end_date]:
    - SL còn đang thuê (trả sau kỳ hoặc chưa trả): tính bình thường [max(giao, đầu kỳ) → cuối kỳ].
    - SL trả trong kỳ này: tính dồn tới hết kỳ tối thiểu [max(giao, đầu kỳ) → max(ngày trả, giao + kỳ tối thiểu)].
    - SL đã trả ở kỳ trước: đã được tính đủ ở tháng trả → bỏ qua.
    """
    map_product_id_2_ratio_price = contract_line_ratios_by_template(contract, end_date)
    transport_lines = _transport_lines_for_billing(env, contract, end_date)
    # Mô phỏng lô theo từng sản phẩm (khớp trả LIFO, lô mới nhất trước).
    lots_by_product = defaultdict(list)  # pid -> list lot dict {d, qty, returns:[(r, q)], open}
    open_stack = defaultdict(list)       # pid -> LIFO các lô còn mở
    orphan_returns = []                  # (product, ngày trả, qty) — trả vượt số đang mở (dữ liệu lệch)
    excess_pool = defaultdict(float)     # pid -> SL chuyển thừa đang giữ (không tính tiền)
    product_by_id = {}

    def _consume_lots(pid, product, ldate, remaining):
        while remaining > 0 and open_stack[pid]:
            lot = open_stack[pid][-1]
            take = min(remaining, lot["open"])
            lot["returns"].append((ldate, take))
            lot["open"] -= take
            remaining -= take
            if lot["open"] <= 0:
                open_stack[pid].pop()
        if remaining > 0:
            orphan_returns.append((product, ldate, remaining))

    for line in transport_lines:
        product = line.product_id
        pid = product.id
        ldate = line.start_rental_or_return_date
        ttype = line.transport_id.type
        if ttype == "return":
            # Trả hàng: ƯU TIÊN trừ phần chuyển thừa trước (không tính tiền/phạt),
            # phần còn lại mới khớp LIFO vào các lô tính tiền (logic hiện tại).
            physical = line.qty or 0
            if not physical:
                continue
            product_by_id[pid] = product
            ex_take = min(physical, excess_pool[pid])
            excess_pool[pid] -= ex_take
            _consume_lots(pid, product, ldate, physical - ex_take)
            continue
        if ttype == "compensation":
            # Đền bù: coi như trả hàng tính tiền (khớp LIFO), không đụng chuyển thừa.
            billable = line.billable_qty
            if not billable:
                continue
            product_by_id[pid] = product
            _consume_lots(pid, product, ldate, billable)
            continue
        # Giao hàng: phần tính tiền vào lô; phần chuyển thừa cộng vào pool (không tính tiền).
        nb = line.non_billable_qty or 0
        billable = line.billable_qty
        if nb:
            product_by_id[pid] = product
            excess_pool[pid] += nb
        if billable:
            product_by_id[pid] = product
            lot = {"d": ldate, "qty": billable, "returns": [], "open": billable}
            lots_by_product[pid].append(lot)
            open_stack[pid].append(lot)

    map_lines = {}
    seq = {"n": 0}

    def _add_line(product, line_start, line_end, qty, deliver_date, kind="present", return_date=None, min_months=0):
        if not qty:
            return
        seq["n"] += 1
        key = "%s_%s_%s_%s" % (
            product.id,
            line_start.strftime("%Y%m%d"),
            line_end.strftime("%Y%m%d"),
            seq["n"],
        )
        map_lines[key] = _build_billing_line_dict(
            env,
            contract,
            map_product_id_2_ratio_price,
            product,
            line_start,
            line_end,
            qty,
            deliver_date,
            start_date,
            end_date,
            kind=kind,
            return_date=return_date,
            min_months=min_months,
        )

    for pid, lots in lots_by_product.items():
        product = product_by_id[pid]
        min_months = _minimum_rental_months(contract, product)
        for lot in lots:
            d = lot["d"]
            if d > end_date:
                continue
            returned_before = sum(q for (r, q) in lot["returns"] if r < start_date)
            returned_in = [(r, q) for (r, q) in lot["returns"] if start_date <= r <= end_date]
            present_qty = lot["qty"] - returned_before - sum(q for (_r, q) in returned_in)
            line_start = max(d, start_date)
            # SL còn đang thuê trong kỳ → tính bình thường tới cuối kỳ.
            _add_line(product, line_start, end_date, present_qty, d, kind="present", min_months=min_months)
            # Kỳ tối thiểu N tháng kể từ ngày giao kết thúc vào NGÀY CUỐI của kỳ
            # (giao 01/06, 2 tháng → 31/07), nên trừ 1 ngày so với mốc +N tháng.
            min_end = (
                d + relativedelta(months=min_months) - relativedelta(days=1)
                if min_months
                else d
            )
            # SL trả trong kỳ: nếu trả sớm (chưa đủ kỳ tối thiểu) → tính dồn tới hết kỳ
            # tối thiểu và gắn nhãn "minimum"; nếu trả đúng/sau kỳ → nhãn "returned".
            for (r, q) in returned_in:
                bill_end = max(r, min_end)
                is_early = bool(min_months) and min_end > r
                _add_line(
                    product,
                    line_start,
                    bill_end,
                    q,
                    d,
                    kind="minimum" if is_early else "returned",
                    return_date=r,
                    min_months=min_months,
                )

    # Trả vượt số đang mở (dữ liệu lệch): hạch toán phần âm tại ngày trả thực.
    for (product, r, q) in orphan_returns:
        if r > end_date:
            continue
        line_start = max(r, start_date)
        _add_line(product, line_start, end_date, -q, r, kind="present")

    # Với mẫu nhiều biến thể tính theo mét dài: khớp trả hàng theo POOL mét dài gộp toàn
    # mẫu (không theo từng biến thể) để phần trả dồn về lô giao mới nhất theo ngày — KH
    # đối chiếu theo tổng mét thuê/trả của sản phẩm, không theo từng kích thước cây.
    _apply_pooled_returns_by_template(
        env, contract, start_date, end_date, map_product_id_2_ratio_price, map_lines, seq
    )

    return map_lines


def _apply_pooled_returns_by_template(env, contract, start_date, end_date, ratios, map_lines, seq):
    """Thay phần KHỚP TRẢ (minimum/returned + trả vượt) của mẫu nhiều biến thể mét dài.

    Phần "đang thuê" (kind=present, qty>=0) giữ nguyên từ khớp theo biến thể (tổng tồn
    bất biến, gộp hiển thị về 1 dòng). Chỉ phần trả được quy đổi sang mét dài và khớp
    LIFO trên POOL gộp toàn mẫu, rồi phát lại theo đúng biến thể được trả (số cây =
    mét/hệ số) để hàng gộp + đơn giá/mét vẫn chính xác.
    """
    from odoo.addons.rental.models.rental_transport_matrix import (
        _linear_meter_factor_for_product,
    )

    Product = env["product.product"]
    Template = env["product.template"]
    tmpl_ids = {Product.browse(v["product_id"]).product_tmpl_id.id for v in map_lines.values()}
    for tmpl_id in tmpl_ids:
        tmpl = Template.browse(tmpl_id)
        variants = tmpl.product_variant_ids
        # Chỉ áp dụng cho mẫu NHIỀU biến thể & toàn bộ là biến thể mét dài (đồng giá/mét).
        if len(variants) <= 1:
            continue
        if any(_linear_meter_factor_for_product(v) is None for v in variants):
            continue
        pooled = _pooled_return_lines_for_template(
            env, contract, tmpl, start_date, end_date, ratios, _linear_meter_factor_for_product
        )
        if pooled is None:
            continue
        # Bỏ các dòng trả cũ (khớp theo biến thể) của mẫu này; giữ lại "đang thuê".
        to_del = [
            k
            for k, v in map_lines.items()
            if Product.browse(v["product_id"]).product_tmpl_id.id == tmpl_id
            and (v["kind"] in ("minimum", "returned") or (v["kind"] == "present" and v["qty"] < 0))
        ]
        for k in to_del:
            del map_lines[k]
        for line in pooled:
            seq["n"] += 1
            map_lines["pool_%s_%s" % (tmpl_id, seq["n"])] = line


def _pooled_return_lines_for_template(env, contract, tmpl, start_date, end_date, ratios, factor_fn):
    """Khớp trả LIFO trên POOL mét dài gộp toàn mẫu; phát dòng trả theo từng lần trả.

    POOL = các "lô" giao (ngày giao, mét còn mở, ngày cuối kỳ tối thiểu) gộp mọi biến thể.
    Mỗi lần trả (biến thể V, q cây) → m = q×hệ_số mét, trừ chuyển thừa trước, rồi LIFO
    lấy mét từ lô giao mới nhất. Mỗi mảnh lấy được phát thành 1 dòng theo biến thể V
    (số cây = mét/hệ_số) với ngày giao = ngày của lô (có thể là lô của biến thể khác).
    """
    min_months = _minimum_rental_months(contract, tmpl.product_variant_ids[:1])
    lines = _transport_lines_for_billing(
        env,
        contract,
        end_date,
        extra_domain=[("product_tmpl_id", "=", tmpl.id)],
    )
    EPS = 1e-9
    slots = []  # list of [deliver_date, meters_open, min_end_lastday]
    excess = 0.0
    out = []

    def _consume(product, factor, r, remaining):
        while remaining > EPS and slots:
            slot = slots[-1]
            take = min(remaining, slot[1])
            if start_date <= r <= end_date and factor:
                d = slot[0]
                min_end = slot[2]
                is_early = bool(min_months) and min_end > r
                out.append(
                    _build_billing_line_dict(
                        env, contract, ratios, product,
                        max(d, start_date), max(r, min_end), take / factor, d,
                        start_date, end_date,
                        kind="minimum" if is_early else "returned",
                        return_date=r, min_months=min_months,
                    )
                )
            slot[1] -= take
            remaining -= take
            if slot[1] <= EPS:
                slots.pop()
        # Trả vượt số đang mở (dữ liệu lệch): hạch toán phần âm tại ngày trả thực.
        if remaining > EPS and start_date <= r <= end_date and factor:
            out.append(
                _build_billing_line_dict(
                    env, contract, ratios, product,
                    max(r, start_date), end_date, -(remaining / factor), r,
                    start_date, end_date, kind="present", return_date=None, min_months=0,
                )
            )

    for line in lines:
        product = line.product_id
        factor = factor_fn(product) or 1.0
        ttype = line.transport_id.type
        r = line.start_rental_or_return_date
        if ttype == "return":
            physical = (line.qty or 0) * factor
            if not physical:
                continue
            ex_take = min(physical, excess)
            excess -= ex_take
            _consume(product, factor, r, physical - ex_take)
            continue
        if ttype == "compensation":
            billable = line.billable_qty
            if not billable:
                continue
            _consume(product, factor, r, billable * factor)
            continue
        # Giao hàng: phần tính tiền vào lô; phần chuyển thừa cộng vào pool (không tính tiền).
        nb = (line.non_billable_qty or 0) * factor
        billable = (line.billable_qty or 0) * factor
        if nb:
            excess += nb
        if billable:
            min_end = (
                r + relativedelta(months=min_months) - relativedelta(days=1)
                if min_months
                else r
            )
            slots.append([r, billable, min_end])
    return out


def _build_map_via_events(env, contract, start_date, end_date):
    """Chi tiết theo product.product + ngày bắt đầu (trước khi gộp mẫu cho Excel).

    Dùng "sự kiện tính tiền" (lô-aware) để hỗ trợ kỳ tối thiểu (TH2) và chuyển dư (TH3).
    Khi không có kỳ tối thiểu/chuyển dư, kết quả tương đương cách tính theo SL ròng cũ.
    """
    map_product_id_2_ratio_price = contract_line_ratios_by_template(contract, end_date)
    events = _build_billing_events(env, contract, end_date)
    map_product_and_date_to_line = {}
    for event in events:
        product = event["product"]
        qty = event["qty"]
        original_start_date = event["date"]
        # Sự kiện sau kỳ (vd ngày trả bị đẩy ra tương lai do kỳ tối thiểu) không ảnh
        # hưởng kỳ này — bỏ qua để không tạo dòng rỗng / trừ nhầm số lượng.
        if original_start_date > end_date:
            continue
        this_line_start_date = original_start_date
        if this_line_start_date < start_date:
            this_line_start_date = start_date

        # "Dư đầu kỳ" CHỈ khi giao trước ngày đầu kỳ; giao đúng ngày đầu kỳ = "Thuê kỳ này".
        is_bob = original_start_date < start_date
        include_start_day = (
            contract.include_start_day_bob
            if original_start_date <= start_date
            else contract.include_start_day_current
        )
        key = f"{product.id}_{this_line_start_date.strftime('%Y%m%d')}_{int(is_bob)}"
        rental_days = rental_days_between_with_holiday(
            env,
            contract,
            this_line_start_date,
            end_date,
            include_start_day=include_start_day,
        )
        tmpl_id = product.product_tmpl_id.id
        ratio = map_product_id_2_ratio_price.get(tmpl_id, 1.0)
        unit_price_day = unit_price_for_transport_line(contract, product, ratio, end_date)
        unit_price_month = monthly_price_for_transport_line(product, ratio)
        display_unit_price = (
            unit_price_day if contract.rental_billing_mode == "day" else unit_price_month
        )
        if key not in map_product_and_date_to_line:
            map_product_and_date_to_line[key] = {
                "start_date": this_line_start_date,
                "end_date": end_date,
                "product_name": product.display_name,
                "uom_name": product._get_staff_display_uom().name,
                "qty": qty,
                "rental_days": rental_days,
                "unit_price": unit_price_day,
                "display_unit_price": display_unit_price,
                "total_amount": rental_days * qty * unit_price_day,
                "is_bob": is_bob,
                "kind": "present",
                "deliver_date": original_start_date,
                "return_date": None,
                "product_id": product.id,
            }
        else:
            map_product_and_date_to_line[key]["qty"] += qty
            map_product_and_date_to_line[key]["total_amount"] += rental_days * qty * unit_price_day
    return map_product_and_date_to_line


def _merge_variant_lines_to_template_row(env, contract, tmpl, variant_lines):
    """Một dòng Excel: mẫu SP + kỳ; SL = Σ(qty×m) nếu nhiều biến thể, ngược lại Σ qty."""
    from odoo.addons.rental.models.rental_transport_matrix import _linear_meter_factor_for_product

    Product = env["product.product"]
    variant_lines = sorted(variant_lines, key=lambda l: Product.browse(l["product_id"]).display_name)
    total_amount = sum(x["total_amount"] for x in variant_lines)
    rental_days = variant_lines[0]["rental_days"]
    end_date = variant_lines[0]["end_date"]
    start_date = variant_lines[0]["start_date"]
    variants = tmpl.product_variant_ids
    if len(variants) <= 1:
        qsum = sum(x["qty"] for x in variant_lines)
        up0 = variant_lines[0]["unit_price"]
        up = (total_amount / (qsum * rental_days)) if qsum and rental_days else up0
        dim = month_day_basis(contract, end_date) if end_date else 0
        display_up = up if contract.rental_billing_mode == "day" else (up * dim if dim else up)
        only_pid = variants[:1].id if variants else variant_lines[0]["product_id"]
        return {
            "start_date": start_date,
            "end_date": end_date,
            "product_name": tmpl.display_name,
            "uom_name": tmpl.uom_id.name if tmpl.uom_id else "",
            "qty": qsum,
            "rental_days": rental_days,
            "unit_price": up,
            "display_unit_price": display_up,
            "total_amount": total_amount,
            "is_bob": variant_lines[0].get("is_bob", False),
            "include_start_day": variant_lines[0].get("include_start_day", False),
            "kind": variant_lines[0].get("kind", "present"),
            "deliver_date": variant_lines[0].get("deliver_date", start_date),
            "return_date": variant_lines[0].get("return_date"),
            "min_months": variant_lines[0].get("min_months", 0),
            "product_id": only_pid,
            "tmpl_id": tmpl.id,
        }
    md = 0.0
    plain = 0.0
    for x in variant_lines:
        prod = Product.browse(x["product_id"])
        q = x["qty"]
        factor = _linear_meter_factor_for_product(prod)
        if factor is not None:
            md += q * factor
        else:
            plain += q
    qty_disp = md + plain
    up = (total_amount / (qty_disp * rental_days)) if qty_disp and rental_days else 0.0
    dim = month_day_basis(contract, end_date) if end_date else 0
    display_up = up if contract.rental_billing_mode == "day" else (up * dim if dim else up)
    return {
        "start_date": start_date,
        "end_date": end_date,
        "product_name": tmpl.display_name,
        "uom_name": tmpl.uom_id.name if tmpl.uom_id else "",
        "qty": qty_disp,
        "rental_days": rental_days,
        "unit_price": up,
        "display_unit_price": display_up,
        "total_amount": total_amount,
        "is_bob": variant_lines[0].get("is_bob", False),
        "include_start_day": variant_lines[0].get("include_start_day", False),
        "kind": variant_lines[0].get("kind", "present"),
        "deliver_date": variant_lines[0].get("deliver_date", start_date),
        "return_date": variant_lines[0].get("return_date"),
        "min_months": variant_lines[0].get("min_months", 0),
        "product_id": variants[:1].id,
        "tmpl_id": tmpl.id,
    }


def calc_rental_payment_table_grouped_by_template(env, contract, start_date, end_date):
    """
    Giống cấu trúc calc_rental_contract_invoice nhưng mỗi khối theo product.template:
    - Nhiều biến thể: gộp theo (mẫu, ngày bắt đầu), SL = Σ(qty_i × mét_i), ĐVT = uom mẫu.
    - Một biến thể: giữ một dòng theo mẫu + kỳ.
    """
    map_product_and_date_to_line = _build_map_product_and_date_to_line(env, contract, start_date, end_date)
    buckets = defaultdict(list)
    for _k, line in map_product_and_date_to_line.items():
        tmpl_id = env["product.product"].browse(line["product_id"]).product_tmpl_id.id
        # Gộp theo (mẫu, lô giao, kỳ tính tiền, phân khúc, loại dòng, ngày trả): mỗi lần
        # giao/trả tách dòng riêng để nhân viên đối chiếu được với phiếu giao/nhận.
        buckets[(
            tmpl_id,
            line["deliver_date"],
            line["start_date"],
            line["end_date"],
            line["is_bob"],
            line["kind"],
            line.get("return_date"),
        )].append(line)

    def _bucket_sort_key(k):
        (_tid, deliver_date, sdate, edate, is_bob, kind, return_date) = k
        kind_order = {"present": 0, "returned": 1, "minimum": 2}.get(kind, 9)
        return (
            _tid,
            deliver_date.toordinal(),
            kind_order,
            (return_date or sdate).toordinal(),
            edate.toordinal(),
            is_bob,
        )

    map_tmpl_id_2_line = {}
    bob_map_tmpl_id_2_line = {}
    for key in sorted(buckets.keys(), key=_bucket_sort_key):
        (tmpl_id, _deliver_date, _sdate, _edate, is_bob, _kind, _rdate) = key
        tmpl = env["product.template"].browse(tmpl_id)
        mline = _merge_variant_lines_to_template_row(env, contract, tmpl, buckets[key])
        tid = mline["tmpl_id"]
        if is_bob:
            map_tmp = bob_map_tmpl_id_2_line
        else:
            map_tmp = map_tmpl_id_2_line
        if tid not in map_tmp:
            map_tmp[tid] = {
                "invoice_qty": mline["qty"] * mline["rental_days"],
                "total_qty": mline["qty"],
                "unit_price": mline["unit_price"],
                "display_unit_price": mline["display_unit_price"],
                "lines": [mline],
            }
        else:
            map_tmp[tid]["total_qty"] += mline["qty"]
            map_tmp[tid]["invoice_qty"] += mline["qty"] * mline["rental_days"]
            map_tmp[tid]["lines"].append(mline)
    return bob_map_tmpl_id_2_line, map_tmpl_id_2_line


def _excess_info_by_template(env, contract, start_date, end_date):
    """Chuyển thừa (không tính tiền) theo product.template:
    - on_hand: SL đang giữ tại cuối kỳ.
    - returns_by_date: SL chuyển thừa được TRẢ LẠI trong kỳ (theo ngày trả).

    Cùng quy tắc với `_build_map_upfront`: giao cộng phần chuyển thừa; trả ưu tiên trừ
    chuyển thừa trước; đền bù không đụng tới chuyển thừa.
    """
    from odoo.addons.rental.models.rental_transport_matrix import _linear_meter_factor_for_product

    Product = env["product.product"]
    lines = _transport_lines_for_billing(env, contract, end_date)
    pool = defaultdict(float)
    excess_returns = []  # (date, pid, qty)
    for line in lines:
        pid = line.product_id.id
        ttype = line.transport_id.type
        if ttype == "return":
            take = min(line.qty or 0, pool[pid])
            if take:
                pool[pid] -= take
                d = line.start_rental_or_return_date
                if start_date <= d <= end_date:
                    excess_returns.append((d, pid, take))
        elif ttype == "compensation":
            continue
        else:
            pool[pid] += line.non_billable_qty or 0

    def _to_tmpl(pid, q):
        prod = Product.browse(pid)
        tmpl = prod.product_tmpl_id
        if len(tmpl.product_variant_ids) > 1:
            factor = _linear_meter_factor_for_product(prod)
            return tmpl.id, q * (factor if factor is not None else 1)
        return tmpl.id, q

    info = defaultdict(lambda: {"on_hand": 0.0, "returns_by_date": defaultdict(float)})
    for pid, q in pool.items():
        if q > 0:
            tid, qq = _to_tmpl(pid, q)
            info[tid]["on_hand"] += qq
    for (d, pid, q) in excess_returns:
        tid, qq = _to_tmpl(pid, q)
        info[tid]["returns_by_date"][d] += qq
    return info


def _merge_display_lines(lines):
    """Gộp các dòng tính tiền giống nhau (cùng kỳ + đơn giá + số ngày) → 1 dòng.

    Dùng cho phần "thuê bình thường" để các lô dư đầu kỳ (cùng hiển thị đầu kỳ → cuối kỳ)
    không bị tách thành nhiều dòng trùng nhau.
    """
    merged = {}
    order = []
    for l in lines:
        key = (
            l["start_date"],
            l["end_date"],
            l["rental_days"],
            round(l.get("display_unit_price", l["unit_price"]), 6),
            bool(l.get("is_bob")),
        )
        if key not in merged:
            merged[key] = dict(l)
            order.append(key)
        else:
            merged[key]["qty"] += l["qty"]
            merged[key]["total_amount"] += l["total_amount"]
    return [merged[k] for k in order]


def calc_rental_payment_blocks_by_template(env, contract, start_date, end_date):
    """Khối thanh toán theo TỪNG product.template (layout: 1 sản phẩm = 1 khối).

    Mỗi khối:
    - normal_lines: dòng thuê bình thường — dư đầu kỳ GỘP 1 dòng (kể cả lô bị trả, chỉ
      phần còn thuê) + lô thuê kỳ này KHÔNG bị trả.
    - return_calc (chỉ khi có trả trong kỳ):
        + offset_deliveries: SL đã thuê để đối ứng — lô thuê kỳ này bị trả (đủ lô) và
          phần "Dư đầu kỳ" CHỈ lấy đúng số lượng cần đối ứng (không số ngày).
        + returns: các lần trả trong kỳ (gộp theo ngày trả) — hiển thị âm/đỏ.
        + leftover_present: phần dư còn thuê của lô THUÊ KỲ NÀY bị trả → tính bình thường.
        + penalty_rows: phần trả bị phạt, gộp theo số ngày tính (phạt đủ kỳ tối thiểu).
        + returned_rows: phần trả không phạt (lô đã quá kỳ tối thiểu), gộp theo (số ngày, ngày trả).
    - present_total_qty: tổng SL đang thuê cuối kỳ (dòng "Cộng").
    - display_unit_price: đơn giá đại diện để hiển thị ở phần đối ứng.
    """
    map_product_and_date_to_line = _build_map_product_and_date_to_line(env, contract, start_date, end_date)
    buckets = defaultdict(list)
    for _k, line in map_product_and_date_to_line.items():
        tmpl_id = env["product.product"].browse(line["product_id"]).product_tmpl_id.id
        buckets[(
            tmpl_id,
            line["deliver_date"],
            line["start_date"],
            line["end_date"],
            line["is_bob"],
            line["kind"],
            line.get("return_date"),
        )].append(line)

    lines_by_tmpl = defaultdict(list)
    for key, blines in buckets.items():
        tmpl = env["product.template"].browse(key[0])
        mline = _merge_variant_lines_to_template_row(env, contract, tmpl, blines)
        lines_by_tmpl[mline["tmpl_id"]].append(mline)

    # Chuyển thừa (không tính tiền) — hiển thị cả khi mẫu KHÔNG có dòng tính tiền nào.
    excess_info = _excess_info_by_template(env, contract, start_date, end_date)

    blocks = []
    all_tmpl_ids = set(lines_by_tmpl) | set(excess_info)
    for tmpl_id in sorted(
        all_tmpl_ids,
        key=lambda t: env["product.template"].browse(t).display_name or "",
    ):
        tmpl = env["product.template"].browse(tmpl_id)
        mlines = lines_by_tmpl.get(tmpl_id, [])
        display_price = next(
            (l.get("display_unit_price", l["unit_price"]) for l in mlines), 0.0
        )
        # Lô (theo ngày giao) bị "động" = có phần trả trong kỳ.
        touched_dates = {l["deliver_date"] for l in mlines if l["kind"] in ("minimum", "returned")}
        # SL đã giao của các lô THUÊ KỲ NÀY bị trả (= dư còn thuê + phần trả) → đối ứng đủ lô.
        this_month_lot_qty = defaultdict(float)
        for l in mlines:
            if not l["is_bob"]:
                this_month_lot_qty[l["deliver_date"]] += l["qty"]

        # Phần "thuê bình thường":
        # - Dư đầu kỳ (is_bob present): luôn gộp về 1 dòng, kể cả lô bị trả → chỉ tách
        #   ĐÚNG số lượng cần đối ứng (phần trả) ra khối tính toán, phần còn lại ở đây.
        # - Thuê kỳ này, lô KHÔNG bị trả: giữ nguyên.
        normal_present = []
        leftover_present = []   # dư còn thuê của lô THUÊ KỲ NÀY bị trả (vd 126)
        returns_by_date = defaultdict(float)
        penalty_by_lot = {}     # gộp phần phạt theo từng lô (deliver_date)
        returned_by_lot = {}    # gộp phần trả thường theo (lô, ngày trả)
        bob_offset_qty = 0.0
        for l in mlines:
            kind = l["kind"]
            if kind == "present":
                if not l["qty"]:
                    continue
                if l["is_bob"] or l["deliver_date"] not in touched_dates:
                    normal_present.append(l)
                else:
                    leftover_present.append(l)
                continue
            # minimum / returned (phần trả)
            if l.get("return_date"):
                returns_by_date[l["return_date"]] += l["qty"]
            if l["is_bob"]:
                bob_offset_qty += l["qty"]
            if kind == "minimum":
                # Mỗi lô (ngày giao) một dòng phạt — text ghi rõ "thuê từ {ngày giao}".
                agg = penalty_by_lot.setdefault(l["deliver_date"], {
                    "qty": 0.0,
                    "total_amount": 0.0,
                    "rental_days": l["rental_days"],
                    "deliver_date": l["deliver_date"],
                    "start_date": l["start_date"],
                    "end_date": l["end_date"],
                    "return_date": l.get("return_date"),
                    "min_months": l.get("min_months", 0),
                    "unit_price": l["unit_price"],
                    "display_unit_price": l.get("display_unit_price", l["unit_price"]),
                    "include_start_day": l.get("include_start_day", False),
                    "is_bob": l.get("is_bob", False),
                })
            else:
                rkey = (l["deliver_date"], l.get("return_date"))
                agg = returned_by_lot.setdefault(rkey, {
                    "qty": 0.0,
                    "total_amount": 0.0,
                    "rental_days": l["rental_days"],
                    "deliver_date": l["deliver_date"],
                    "start_date": l["start_date"],
                    "end_date": l["end_date"],
                    "return_date": l.get("return_date"),
                    "min_months": l.get("min_months", 0),
                    "unit_price": l["unit_price"],
                    "display_unit_price": l.get("display_unit_price", l["unit_price"]),
                    "include_start_day": l.get("include_start_day", False),
                    "is_bob": l.get("is_bob", False),
                })
            agg["qty"] += l["qty"]
            agg["total_amount"] += l["total_amount"]

        # Gộp các dòng thuê bình thường giống nhau (cùng kỳ/đơn giá) → 1 dòng (dư đầu kỳ).
        normal_lines = _merge_display_lines(normal_present)
        normal_lines.sort(key=lambda l: (0 if l.get("is_bob") else 1, l["start_date"]))
        leftover_present.sort(key=lambda l: (l["deliver_date"], l["start_date"]))
        present_total = sum(l["qty"] for l in normal_lines) + sum(l["qty"] for l in leftover_present)

        exc = excess_info.get(tmpl_id, {"on_hand": 0.0, "returns_by_date": {}})
        excess_returns_by_date = exc["returns_by_date"]
        excess_return_total = sum(excess_returns_by_date.values())

        return_calc = None
        if touched_dates or excess_return_total:
            offset_deliveries = []
            for d in sorted(td for td in touched_dates if td >= start_date):
                offset_deliveries.append({"date": d, "qty": this_month_lot_qty[d], "is_bob": False})
            if bob_offset_qty:
                # Chỉ lấy đúng số lượng cần đối ứng từ dư đầu kỳ.
                offset_deliveries.append({"date": None, "qty": bob_offset_qty, "is_bob": True})
            # Phần trả ĐỎ hiển thị ĐỦ số vật lý = phần tính tiền + phần chuyển thừa trả lại.
            phys_dates = set(returns_by_date) | set(excess_returns_by_date)
            physical_returns = [
                {"date": d, "qty": returns_by_date.get(d, 0.0) + excess_returns_by_date.get(d, 0.0)}
                for d in sorted(phys_dates)
            ]
            return_calc = {
                "offset_deliveries": offset_deliveries,
                "excess_return_qty": excess_return_total,
                "returns": physical_returns,
                "leftover_present": leftover_present,
                "penalty_rows": [penalty_by_lot[k] for k in sorted(penalty_by_lot)],
                "returned_rows": [
                    returned_by_lot[k]
                    for k in sorted(returned_by_lot, key=lambda x: (x[0], x[1] or start_date))
                ],
            }

        blocks.append({
            "tmpl_id": tmpl_id,
            "product_name": tmpl.display_name,
            "uom_name": tmpl.uom_id.name if tmpl.uom_id else "",
            "display_unit_price": display_price,
            "normal_lines": normal_lines,
            "return_calc": return_calc,
            "present_total_qty": present_total,
            "excess_qty": exc["on_hand"],
        })
    return blocks


def calc_rented_qty_as_of(
    env,
    as_of_date,
    *,
    contract_ids=None,
    partner_company_ids=None,
    tmpl_ids=None,
    only_active_contracts=False,
):
    """Calculate official rented quantities at the end of ``as_of_date``.

    The result stays contract-granular so users can reconcile each balance with
    its transport history. UI totals provide the customer-wide roll-up.
    """
    if not as_of_date:
        raise ValueError("as_of_date is required")

    domain = [("company_id", "in", env.companies.ids)]
    if contract_ids is not None:
        domain.append(("id", "in", list(contract_ids)))
    if partner_company_ids is not None:
        domain.append(("a_company_party", "in", list(partner_company_ids)))
    if only_active_contracts:
        domain.append(("status", "=", "active"))

    contracts = env["rental.contract"].search(domain, order="a_company_party, code, id")
    wanted_tmpl_ids = set(tmpl_ids or [])
    rows = []
    for contract in contracts:
        blocks = calc_rental_payment_blocks_by_template(
            env, contract, as_of_date, as_of_date
        )
        for block in blocks:
            tmpl_id = block["tmpl_id"]
            if wanted_tmpl_ids and tmpl_id not in wanted_tmpl_ids:
                continue
            rented_qty = max(block["present_total_qty"] or 0.0, 0.0)
            excess_qty = max(block["excess_qty"] or 0.0, 0.0)
            if not rented_qty and not excess_qty:
                continue
            rows.append({
                "contract_id": contract.id,
                "partner_company_id": contract.a_company_party.id,
                "tmpl_id": tmpl_id,
                "product_name": block["product_name"],
                "uom_name": block["uom_name"],
                "rented_qty": rented_qty,
                "excess_qty": excess_qty,
                "physical_qty": rented_qty + excess_qty,
            })
    return rows


def calc_rental_contract_invoice(env, contract, start_date, end_date):
    map_product_and_date_to_line = _build_map_product_and_date_to_line(env, contract, start_date, end_date)

    #  Ok now, we need to group all line by the product_id
    map_product_id_2_line = {}
    bob_map_product_id_2_line = {}  # Beginning outstanding balance
    for product_and_date in map_product_and_date_to_line:
        line = map_product_and_date_to_line[product_and_date]
        product_id = line['product_id']
        if line.get('is_bob'):
            # This is bob: Begining outstanding balance
            map_tmp = bob_map_product_id_2_line
        else:
            map_tmp = map_product_id_2_line
        if product_id not in map_tmp:
            map_tmp[product_id] = {
                'invoice_qty': line['qty'] * line['rental_days'],  # This will be used for Odoo invoice
                'total_qty': line['qty'],
                'unit_price': line['unit_price'],
                'lines': [line]
            }
        else:
            map_tmp[product_id]['total_qty'] += line['qty']
            map_tmp[product_id]['invoice_qty'] += line['qty'] * line['rental_days']
            map_tmp[product_id]['lines'].append(line)
    return bob_map_product_id_2_line, map_product_id_2_line

