"""add_e9y_member_id_mt

Revision ID: e759604e4726
Revises: 4953578418c8
Create Date: 2024-09-03 23:52:04.978834+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "e759604e4726"
down_revision = "4953578418c8"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE member_track ADD COLUMN new_eligibility_member_id BIGINT,
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
            ALTER TABLE member_track DROP COLUMN new_eligibility_member_id,
            ALGORITHM=INPLACE,
            LOCK=NONE;
            """
    )
