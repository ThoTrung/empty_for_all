#!/usr/bin/env bash
# Debug import Excel — chạy trong Docker Odoo đang chạy.
#
# Cách dùng:
#   1. Copy file Excel vào tests/fixtures/import_sample.xlsx (hoặc đường dẫn khác)
#   2. ./scripts/debug_transport_import.sh [đường_dẫn_xlsx] [mã_hợp_đồng]
#
# Ví dụ:
#   ./scripts/debug_transport_import.sh tests/fixtures/import_sample.xlsx HD-2026-001
#
set -euo pipefail

CONTAINER="${ODOO_CONTAINER:-odoobase-x_odoo_aitilen-1}"
XLSX_REL="${1:-tests/fixtures/import_sample.xlsx}"
CONTRACT_CODE="${2:-}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MODULE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
XLSX_HOST="$MODULE_DIR/$XLSX_REL"
XLSX_CONTAINER="/mnt/extra-addons/odoo_modules/rental/$XLSX_REL"

if [[ ! -f "$XLSX_HOST" ]]; then
  echo "Không tìm thấy file: $XLSX_HOST"
  echo "Hãy copy file Excel vào tests/fixtures/import_sample.xlsx rồi chạy lại."
  exit 1
fi

docker exec -i "$CONTAINER" bash -lc "odoo shell -c /etc/odoo/odoo.conf -d rental --db_host=x_db --db_user=odoo --db_password=\"\$PASSWORD\"" <<PY
import base64
from pathlib import Path
from odoo.addons.rental.helper.import_transport_matrix import parse_transport_matrix_xlsx

path = Path("$XLSX_CONTAINER")
if not path.is_file():
    raise SystemExit(f"Trong container không thấy: {path}")

contract_code = """$CONTRACT_CODE""".strip() or None
if contract_code:
    contract = env["rental.contract"].search([("code", "=", contract_code)], limit=1)
    if not contract:
        contract = env["rental.contract"].search([("name", "ilike", contract_code)], limit=1)
else:
    contract = env["rental.contract"].search([], limit=1)

if not contract:
    raise SystemExit("Không tìm thấy hợp đồng. Truyền mã HĐ làm tham số thứ 2.")

print("=" * 60)
print(f"File: {path.name}")
print(f"Hợp đồng: {contract.code} (id={contract.id})")
print("=" * 60)

parsed = parse_transport_matrix_xlsx(path.read_bytes(), env, contract=contract)

print(f"Dòng parse được: {len(parsed['rows'])}")
print(f"Lỗi mapping SP: {len(parsed.get('product_mapping_errors') or [])}")
print(f"Cảnh báo: {len(parsed.get('warnings') or [])}")
print()

if parsed.get("product_mapping_errors"):
    print("--- LỖI MAPPING SẢN PHẨM ---")
    for i, item in enumerate(parsed["product_mapping_errors"], 1):
        print(f"{i}) Cột {item['col_letter']} — «{item['excel_label']}»")
        print(item["detail"])
        print()

print("--- XEM TRƯỚC DÒNG ---")
for row in parsed["rows"]:
    status = "LỖI" if row.get("errors") else "OK"
    lines = ", ".join(f"pid={p} x{q}" for p, q in (row.get("lines") or []))
    print(
        f"[{status}] dòng Excel {row['row_number']}: "
        f"{row.get('transport_date')} | {row.get('plate')} | "
        f"{row.get('transport_type')} | {lines or '(không có SP)'}"
    )
    for err in row.get("errors") or []:
        print(f"    ! {err}")

if parsed.get("warnings"):
    print()
    print("--- CẢNH BÁO ---")
    for w in parsed["warnings"]:
        print(f"  - {w}")
PY
