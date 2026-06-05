# -*- coding: utf-8 -*-
"""Drop obsolete unique constraint on rental.template (blocked multiple uploads per type)."""


def migrate(cr, version):
    cr.execute(
        """
        ALTER TABLE rental_template
        DROP CONSTRAINT IF EXISTS rental_template_template_unique_per_file_company
        """
    )
