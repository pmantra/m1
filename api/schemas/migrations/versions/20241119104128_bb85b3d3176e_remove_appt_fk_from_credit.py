"""remove_appt_fk_from_credit

Revision ID: bb85b3d3176e
Revises: 4bcaea3f8578
Create Date: 2024-11-19 10:41:28.133754+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "bb85b3d3176e"
down_revision = "bc5095412713"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE credit
        DROP FOREIGN KEY credit_ibfk_2,
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE credit
        ADD CONSTRAINT credit_ibfk_2 FOREIGN KEY (appointment_id) REFERENCES appointment(id),
        ALGORITHM=COPY, LOCK=SHARED;
        """
    )
