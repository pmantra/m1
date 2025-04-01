"""add_eligibility_member_id_to_credit_table

Revision ID: c469e0357e1b
Revises: c91093fae227
Create Date: 2023-06-06 18:05:54.521604+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "c469e0357e1b"
down_revision = "0da44cfc80ce"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE maven.credit
        ADD COLUMN eligibility_member_id int(11) DEFAULT NULL,
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE maven.credit
        DROP COLUMN eligibility_member_id,
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )
