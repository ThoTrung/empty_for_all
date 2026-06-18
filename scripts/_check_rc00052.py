c = env["rental.contract"].search([("code", "=", "RC00052")], limit=1)
if not c:
    print("NO CONTRACT")
else:
    print("contract", c.id, c.code, "status", c.status)
    transports = env["rr.transport"].sudo().search([("rental_contract_id", "=", c.id)])
    print("transports", len(transports))
    for t in transports:
        print(" ", t.code, t.start_rental_or_return_date, t.plate, t.state, "lines", len(t.transport_line_ids))
