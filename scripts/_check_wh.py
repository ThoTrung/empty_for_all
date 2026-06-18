c = env["rental.contract"].search([("code", "=", "RC00052")], limit=1)
co = c.company_id
print("company", co.id, co.name)
whs = env["stock.warehouse"].sudo().search([("company_id", "=", co.id)])
print("warehouses for contract co", whs.mapped("name"))
for wh in env["stock.warehouse"].sudo().search([]):
    print(" WH", wh.name, "co", wh.company_id.name, "out", wh.out_type_id.id)
