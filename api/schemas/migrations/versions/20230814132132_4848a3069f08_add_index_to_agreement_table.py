"""add_index_to_agreement_table

Revision ID: 4848a3069f08
Revises: 48f06e0e92dd
Create Date: 2023-08-14 13:21:32.955956+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "4848a3069f08"
down_revision = "48f06e0e92dd"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `agreement`
        ADD INDEX ix_agreement_name_version (name, version),
        ALGORITHM=INPLACE,
        LOCK=NONE
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `agreement`
        DROP INDEX ix_agreement_name_version,
        ALGORITHM=INPLACE,
        LOCK=NONE
        """
    )
