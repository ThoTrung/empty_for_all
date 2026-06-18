import base64
from pathlib import Path

path = Path("/mnt/extra-addons/odoo_modules/rental/tests/fixtures/import delivery.xlsx")
contract = env["rental.contract"].search([("code", "=", "RC00052")], limit=1)
driver = env["res.partner"].search([("customer_type", "=", "driver")], limit=1)
env["rr.transport"].sudo().search([("rental_contract_id", "=", contract.id), ("state", "=", "draft")]).unlink()

wizard = env["rental.transport.import.wizard"].create({
    "rental_contract_id": contract.id,
    "default_driver_id": driver.id,
    "validate_picking": True,
    "import_file": base64.b64encode(path.read_bytes()),
    "import_filename": "import delivery.xlsx",
})
try:
    wizard.action_import_transports()
    print("FULL IMPORT OK")
except Exception as e:
    print("FULL IMPORT FAIL", str(e)[:300])

done = env["rr.transport"].sudo().search_count([("rental_contract_id", "=", contract.id), ("state", "=", "done")])
draft = env["rr.transport"].sudo().search_count([("rental_contract_id", "=", contract.id), ("state", "=", "draft")])
print("done", done, "draft", draft)
