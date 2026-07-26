# -*- coding: utf-8 -*-


def migrate(cr, version):
    """Copy is_doctor_route → booking_board before schema drops is_doctor_route."""
    cr.execute(
        """
        SELECT 1
        FROM information_schema.tables
        WHERE table_name = 'spa_service_booking'
        """
    )
    if not cr.fetchone():
        return

    cr.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'spa_service_booking'
          AND column_name = 'booking_board'
        """
    )
    if not cr.fetchone():
        cr.execute(
            """
            ALTER TABLE spa_service_booking
            ADD COLUMN booking_board VARCHAR
            """
        )

    cr.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'spa_service_booking'
          AND column_name = 'is_doctor_route'
        """
    )
    if cr.fetchone():
        cr.execute(
            """
            UPDATE spa_service_booking
            SET booking_board = CASE
                WHEN is_doctor_route IS TRUE THEN 'doctor'
                ELSE 'specialist'
            END
            """
        )
    else:
        cr.execute(
            """
            UPDATE spa_service_booking
            SET booking_board = 'specialist'
            WHERE booking_board IS NULL
            """
        )

    cr.execute(
        """
        UPDATE spa_service_booking
        SET booking_board = 'specialist'
        WHERE booking_board IS NULL
           OR booking_board NOT IN ('doctor', 'specialist')
        """
    )
    cr.execute(
        """
        ALTER TABLE spa_service_booking
        ALTER COLUMN booking_board SET DEFAULT 'specialist'
        """
    )
    cr.execute(
        """
        ALTER TABLE spa_service_booking
        ALTER COLUMN booking_board SET NOT NULL
        """
    )
