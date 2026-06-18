# Rental reference (on-demand)

> Entry: `AGENTS.md`. File này khi cần chi tiết model/security/workflow.

## Models

**Owned:** `rental.contract`(line), `rr.transport`(line), `rental.transport.matrix`, `rental.invoice`(line, legacy), `construction.*`, `transport.truck`, `rental.template`, `rental.product.template.set`, `rental.holiday`, `mc.group.mixin`, `amount_to_text.vi`

**Inherit:** `res.partner`(customer_type), `res.users`(leader), `product.*`(rental price/multiplier/uom), `stock.picking`→transport done, `account.move`(rental fields)

**Wizards:** `create.invoice`, `rental.reject.confirm`, `rental.transport.matrix.overlap`, `rental.transport.import`, `rental.link.child.contact`

**Services** (`rental_contract_services.py`): `rental_days_between_with_holiday`, `unit_price_for_transport_line`, `calc_rental_*`, `render_rental_contract_docx`

## Contract (`rental.contract`)

- A=renter, B=current company branch
- States: `new`→`need_approve`→`leader_approved`→`customer_confirmed`→`active`→`finish` (`need_fix`,`break`)
- Lock: `can_edit` / `edit_unlocked`; blocked `write()` unless `rental_contract_allow_locked_write`
- Billing: `rental_billing_mode` day|month; `include_start_day_*`

## Transport & matrix

- `rr.transport`: delivery|return → `stock.picking`; picking done → `transport.state=done` (sudo)
- Courier: no `perm_write` transport — picking only
- Matrix: no period overlap per contract; column sort by parsed length (`2m`,`1,5m`)

## Security

Groups: staff→leader→manager→admin (implied chain); `group_rental_transport_courier` separate (+stock user)

Rules: `company_id in company_ids`; courier filtered by `deliverer/receiver_partner_id = user.partner_id`

Risks: controller `sudo()`; `rental_contract_id` on transport has `groups=staff`

## Workflows

**Approve:** `request_confirm`→`need_approve`→`leader_confirm`→`customer_confirm`→`active`→`finish`

**Billing:** transports done → wizard period → `action_export_invoice_excel` / `action_create_rental_invoice` → `account.move` + XLSX

**Matrix:** `action_create_transport_matrix_record` (overlap→wizard) → export via controller

## Depends & tests

Manifest: `base,web,stock,sale,sale_management` — needs `account`,`mail` at runtime

Python: `openpyxl`, `docxtpl`, `docx2pdf`/LibreOffice

Tests: `test_rental_holiday_days`, `test_rental_transport_matrix_overlap`, `test_transport_import`

## Pitfalls

| Issue | Fix |
|-------|-----|
| Missing account/mail depends | Add to manifest or pre-install |
| `rental.invoice.line` compute calls `write()` | Assign fields directly |
| Controller sudo IDOR | Check `company_id in env.companies` |
| Courier missing contract field | Use `rental_contract_summary`/picking |
| No rental.template | Fallback `static/file_template/` |

## After change

Log: `WORKLOG.md` · ADR: `DECISIONS.md` · Bug: `BUG_LOG.md`
