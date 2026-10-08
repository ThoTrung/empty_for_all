# -*- coding: utf-8 -*-
def migrate(cr, version):
    cr.execute(
        """
        UPDATE rental_subrent_contract c
        SET policy_code = 'tracked'
        WHERE EXISTS (
            SELECT 1 FROM rental_subrent_lot l
            WHERE l.subrent_contract_id = c.id
        )
        AND (c.policy_code IS NULL OR c.policy_code = 'simple')
        """
    )
