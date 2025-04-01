"""add_e9y_member_id_credit

Revision ID: 4953578418c8
Revises: 7f8d9f740fee
Create Date: 2024-09-03 23:51:50.787314+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "4953578418c8"
down_revision = "7f8d9f740fee"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE credit ADD COLUMN new_eligibility_member_id BIGINT,
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
            ALTER TABLE credit DROP COLUMN new_eligibility_member_id,
            ALGORITHM=INPLACE,
            LOCK=NONE;
            """
    )
