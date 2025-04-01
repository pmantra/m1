"""next-availability-2

Revision ID: 46979b86247b
Revises: 5c5e8821c03d
Create Date: 2025-02-12 22:21:50.352825+00:00

"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "46979b86247b"
down_revision = "5c5e8821c03d"
branch_labels = None
depends_on = None


def upgrade():
    # Somehow the previous script only added the triggers in QA2, so add the DROP statements here
    op.execute(
        """
        DROP TRIGGER IF EXISTS `after_next_availability_update`;
        DROP TRIGGER IF EXISTS `after_next_availability_delete`;
        """
    )

    # Create triggers
    op.execute(
        """
        CREATE TRIGGER after_next_availability_update
            AFTER UPDATE
            ON practitioner_profile
            FOR EACH ROW
            BEGIN
                IF OLD.next_availability != NEW.next_availability THEN
                    UPDATE practitioner_data
                    SET next_availability = NEW.next_availability
                    WHERE user_id = NEW.user_id;
                END IF;
            END
        """
    )

    op.execute(
        """
        CREATE TRIGGER after_next_availability_delete
            AFTER DELETE
            ON practitioner_profile FOR EACH ROW
            BEGIN
                DELETE FROM practitioner_data
                WHERE user_id = OLD.user_id;
            END
        """
    )


def downgrade():
    op.execute(
        """
        DROP TRIGGER IF EXISTS `after_next_availability_update`;
        DROP TRIGGER IF EXISTS `after_next_availability_delete`;
        """
    )
