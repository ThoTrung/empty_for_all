# -*- coding: utf-8 -*-
def migrate(cr, version):
    """Ensure legacy NCC partners use company form mode (flag already on column)."""
    cr.execute(
        """
        SELECT 1
          FROM information_schema.columns
         WHERE table_name = 'res_partner'
           AND column_name = 'is_rental_supplier'
        """
    )
    if not cr.fetchone():
        return
    cr.execute(
        """
        UPDATE res_partner
           SET customer_type = 'company'
         WHERE is_rental_supplier IS TRUE
           AND (
                customer_type IS NULL
                OR customer_type NOT IN (
                    'driver', 'my_company_profile', 'company'
                )
           )
        """
    )
