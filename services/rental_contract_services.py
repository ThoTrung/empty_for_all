import calendar
import base64
import io
from collections import defaultdict
from datetime import date

from odoo.modules.module import get_module_resource
from docxtpl import DocxTemplate


def _get_company_template_stream(contract, template_type, default_filename):
    """Return a file-like object for the template for the contract company."""
    Template = contract.env["rental.template"]
    company = contract.company_id
    template = Template.search(
        [
            ("company_id", "=", company.id),
            ("template_type", "=", template_type),
            ("active", "=", True),
        ],
        order="is_default desc, id desc",
        limit=1,
    )
    if template and template.file_data:
        data = base64.b64decode(template.file_data)
        return io.BytesIO(data)

    # Fallback to module static file
    template_path = get_module_resource(
        "rental",
        "static",
        "file_template",
        default_filename,
    )
    return template_path


def render_rental_contract_docx(contract):
    # Load template and render
    template_stream = _get_company_template_stream(
        contract,
        template_type="contract_docx",
        default_filename="rental_contract_template.docx",
    )
    today = date.today()
    doc = DocxTemplate(template_stream)
    context = {
        'contract_code': contract.code,
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


def contract_line_ratios_by_template(contract):
    """Giá dòng HĐ / list_price mẫu — dùng để quy đổi giá kho khi khác báo giá."""
    ratios = {}
    for rc_line in contract.rental_contract_line_ids:
        tmpl = rc_line.product_tmpl_id
        lp = tmpl.list_price or 0.0
        ratios[tmpl.id] = (rc_line.price_unit / lp) if lp else 1.0
    return ratios


def unit_price_for_transport_line(contract, product, ratio, period_end_date):
    """Đơn giá theo một ngày thuê (đã nhân ratio báo giá), thống nhất Excel + account.move."""
    tmpl = product.product_tmpl_id
    monthly_eff = product.lst_price * ratio
    dim = calendar.monthrange(period_end_date.year, period_end_date.month)[1]
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
    return days


def _build_map_product_and_date_to_line(env, contract, start_date, end_date):
    """Chi tiết theo product.product + ngày bắt đầu (trước khi gộp mẫu cho Excel)."""
    transport_lines = env["rr.transport.line"].search(
        [
            ("transport_id", "in", contract.rr_transport_ids.ids),
            ("start_rental_or_return_date", "<=", end_date),
        ],
        order="start_rental_or_return_date ASC, id ASC",
    )
    map_product_id_2_ratio_price = contract_line_ratios_by_template(contract)
    map_product_and_date_to_line = {}
    for line in transport_lines:
        is_return = line.transport_id.type == "return"
        original_start_date = line.start_rental_or_return_date
        this_line_start_date = original_start_date
        if this_line_start_date < start_date:
            this_line_start_date = start_date

        key = f"{line.product_id.id}_{this_line_start_date.strftime('%Y%m%d')}"
        qty = line.qty * (-1 if is_return else 1)
        is_bob_line = original_start_date <= start_date
        include_start_day = (
            contract.include_start_day_bob if is_bob_line else contract.include_start_day_current
        )
        rental_days = rental_days_between(
            this_line_start_date, end_date, include_start_day=include_start_day
        )
        tmpl_id = line.product_id.product_tmpl_id.id
        ratio = map_product_id_2_ratio_price.get(tmpl_id, 1.0)
        unit_price_day = unit_price_for_transport_line(contract, line.product_id, ratio, end_date)
        unit_price_month = monthly_price_for_transport_line(line.product_id, ratio)
        display_unit_price = (
            unit_price_day if contract.rental_billing_mode == "day" else unit_price_month
        )
        if key not in map_product_and_date_to_line:
            map_product_and_date_to_line[key] = {
                "start_date": this_line_start_date,
                "end_date": end_date,
                "product_name": line.product_id.display_name,
                "uom_name": line.product_id._get_staff_display_uom().name,
                "qty": qty,
                "rental_days": rental_days,
                "unit_price": unit_price_day,
                "display_unit_price": display_unit_price,
                "total_amount": rental_days * qty * unit_price_day,
                "product_id": line.product_id.id,
            }
        else:
            map_product_and_date_to_line[key]["qty"] += qty
            map_product_and_date_to_line[key]["total_amount"] += rental_days * qty * unit_price_day
    return map_product_and_date_to_line


def _merge_variant_lines_to_template_row(env, contract, tmpl, variant_lines):
    """Một dòng Excel: mẫu SP + kỳ; SL = Σ(qty×m) nếu nhiều biến thể, ngược lại Σ qty."""
    from odoo.addons.rental.models.rental_transport_matrix import _parse_length_meters

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
        dim = calendar.monthrange(end_date.year, end_date.month)[1] if end_date else 0
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
            "product_id": only_pid,
            "tmpl_id": tmpl.id,
        }
    md = 0.0
    plain = 0.0
    for x in variant_lines:
        prod = Product.browse(x["product_id"])
        length_m = _parse_length_meters(prod.display_name)
        q = x["qty"]
        if length_m is not None:
            md += q * length_m
        else:
            plain += q
    qty_disp = md + plain
    up = (total_amount / (qty_disp * rental_days)) if qty_disp and rental_days else 0.0
    dim = calendar.monthrange(end_date.year, end_date.month)[1] if end_date else 0
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
        buckets[(tmpl_id, line["start_date"])].append(line)

    map_tmpl_id_2_line = {}
    bob_map_tmpl_id_2_line = {}
    for (tmpl_id, sdate) in sorted(buckets.keys(), key=lambda x: (x[0], x[1].toordinal())):
        tmpl = env["product.template"].browse(tmpl_id)
        mline = _merge_variant_lines_to_template_row(env, contract, tmpl, buckets[(tmpl_id, sdate)])
        tid = mline["tmpl_id"]
        if mline["start_date"] <= start_date:
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


def calc_rental_contract_invoice(env, contract, start_date, end_date):
    map_product_and_date_to_line = _build_map_product_and_date_to_line(env, contract, start_date, end_date)

    #  Ok now, we need to group all line by the product_id
    map_product_id_2_line = {}
    bob_map_product_id_2_line = {}  # Beginning outstanding balance
    for product_and_date in map_product_and_date_to_line:
        line = map_product_and_date_to_line[product_and_date]
        product_id = line['product_id']
        if line['start_date'] <= start_date:
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

