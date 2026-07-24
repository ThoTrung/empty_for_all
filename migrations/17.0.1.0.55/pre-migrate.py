# -*- coding: utf-8 -*-


def migrate(cr, version):
    # Drop stale snapshot rows before unique(company, as_of, contract, tmpl) lands.
    cr.execute(
        """
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_name = 'rental_analytics_on_hire_line'
        """
    )
    if cr.fetchone():
        cr.execute("DELETE FROM rental_analytics_on_hire_line")

    # Old act_window xmlid cannot become ir.actions.server — remove leftover.
    cr.execute(
        """
        DELETE FROM ir_act_window
        WHERE id IN (
            SELECT res_id FROM ir_model_data
            WHERE module = 'rental'
              AND name = 'action_rental_analytics_on_hire'
              AND model = 'ir.actions.act_window'
        )
        """
    )
    cr.execute(
        """
        DELETE FROM ir_model_data
        WHERE module = 'rental'
          AND name = 'action_rental_analytics_on_hire'
        """
    )
