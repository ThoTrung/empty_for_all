# -*- coding: utf-8 -*-
def migrate(cr, version):
    """Map exclusive customer_type=renter → form mode company + Khách thuê flag.

    is_rental_supplier may already exist (rental_subrent); ensure those partners
    use company form mode so they share the company sheet UI.
    """
    cr.execute(
        """
        UPDATE res_partner
           SET is_rental_customer = TRUE,
               customer_type = 'company'
         WHERE customer_type = 'renter'
        """
    )
    cr.execute(
        """
        SELECT 1
          FROM information_schema.columns
         WHERE table_name = 'res_partner'
           AND column_name = 'is_rental_supplier'
        """
    )
    if cr.fetchone():
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
