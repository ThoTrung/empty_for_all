import base64
from pathlib import Path

from odoo.addons.rental.helper.import_transport_matrix import parse_transport_matrix_xlsx

path = Path("/mnt/extra-addons/odoo_modules/rental/tests/fixtures/import delivery.xlsx")
contract = env["rental.contract"].search([("code", "=", "RC00052")], limit=1)
driver = env["res.partner"].search([("customer_type", "=", "driver")], limit=1)
if not driver:
    driver = env["res.partner"].create({"name": "Import Driver", "customer_type": "driver"})

before = env["rr.transport"].sudo().search_count([("rental_contract_id", "=", contract.id)])
wizard = env["rental.transport.import.wizard"].create({
    "rental_contract_id": contract.id,
    "default_driver_id": driver.id,
    "validate_picking": False,
    "import_file": base64.b64encode(path.read_bytes()),
    "import_filename": "import delivery.xlsx",
})
parsed = wizard._parse_uploaded_file()
ok = [r for r in parsed["rows"] if r.get("lines") and not r.get("errors")]
err = [r for r in parsed["rows"] if r.get("errors")]
print("parsed ok", len(ok), "err", len(err))
wizard.action_import_transports()
after = env["rr.transport"].sudo().search_count([("rental_contract_id", "=", contract.id)])
print("transports before", before, "after", after, "created", after - before)
