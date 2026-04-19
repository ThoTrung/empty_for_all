### Convert word to pdf 
For print contract directly on website (no need to download then print)
```shell
pip install docx2pdf
```
For Ubuntu we use
```shell
sudo apt-get install -y libreoffice
```

# Hide all old res_partner form and add new screen structure.
- This allow use display what we need in the res_partner
- Check if it is driver, or it is renter-company
Next: All user edit their own company information, same to this but the action only have form, not have tree, form like above (because we have only one company)

## 2: Display my company form profile
- From menu, we only want to display form of a record, not display tree view.
- The keywork here is: we must add res_id in action, but we must add it in python so we have env.company.partner_id.id,
- For our case, we must add value: my_company_profile to handle res_partner display


## 3: NEXT
- Allow create contract from User, and list all contract of user in User form page.
- Check flow of contract, add button to change status. Depend on status, some feature can be disabled or enable



```shell
./odoo/odoo-bin shell -c /home/tho/project/17.0/conf/odoo_dev.conf --db_host=localhost --db_port=5432 --db_user=odoo --db_password=odoo -d rental -u rental
/usr/bin/odoo shell -c /etc/odoo/odoo.conf --db_host x_db -w odoo -d rental -i rental


./odoo/odoo-bin \
  --db_host=localhost --db_port=5432 --db_user=odoo --db_password=odoo -d rental -u rental \
  -c ./conf/odoo_dev.conf \
  -u rental \
  --stop-after-init
/usr/bin/odoo \
  --db_host x_db -w odoo -d rental -i rental \
  -c /etc/odoo/odoo.conf \
  -u rental \
  --stop-after-init
```

