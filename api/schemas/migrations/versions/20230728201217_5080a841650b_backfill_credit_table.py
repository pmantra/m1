"""backfill_credit_table

Revision ID: 5080a841650b
Revises: 0f02dc2f7ed7
Create Date: 2023-07-28 20:12:17.075621+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "5080a841650b"
down_revision = "0f02dc2f7ed7"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
    UPDATE maven.credit c
        INNER JOIN maven.backfill_credit_state bcs ON bcs.credit_id = c.id
        SET c.eligibility_member_id = bcs.eligibility_member_id
    """
    )


def downgrade():
    op.execute(
        """
    UPDATE maven.credit c
        INNER JOIN maven.backfill_credit_state bcs ON bcs.credit_id = c.id
        SET c.eligibility_member_id = NULL
    """
    )
