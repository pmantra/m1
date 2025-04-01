"""add_eligibility_verification_id_to_credit_table

Revision ID: 1687d347af25
Revises: 25699faf41e4
Create Date: 2023-07-13 16:52:18.712631+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "1687d347af25"
down_revision = "213088d7ee79"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE maven.credit
        ADD COLUMN eligibility_verification_id int(11) DEFAULT NULL,
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE maven.credit
        DROP COLUMN eligibility_verification_id,
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )
