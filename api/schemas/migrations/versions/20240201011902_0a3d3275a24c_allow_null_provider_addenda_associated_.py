"""allow_null_provider_addenda_associated_answer_id

Revision ID: 0a3d3275a24c
Revises: f2b1dbb00734
Create Date: 2024-02-01 01:19:02.199735+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "0a3d3275a24c"
down_revision = "f2b1dbb00734"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `provider_addendum`
        MODIFY COLUMN `associated_answer_id` bigint(20),
        ALGORITHM=COPY, LOCK=SHARED;
        """
    )


def downgrade():
    op.execute("SET SESSION foreign_key_checks = 0")
    op.execute(
        """
        ALTER TABLE `provider_addendum`
        MODIFY COLUMN `associated_answer_id` bigint(20) NOT NULL,
        ALGORITHM=COPY, LOCK=SHARED;
        """
    )
    op.execute("SET SESSION foreign_key_checks = 1")
