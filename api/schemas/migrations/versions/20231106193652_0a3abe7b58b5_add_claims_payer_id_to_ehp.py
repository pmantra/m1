"""add_claims_payer_id_to_ehp

Revision ID: 0a3abe7b58b5
Revises: 6219ce1fefcf
Create Date: 2023-11-06 19:36:52.190227+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "0a3abe7b58b5"
down_revision = "6219ce1fefcf"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `employer_health_plan`
        ADD COLUMN `benefits_payer_id` bigint(20) DEFAULT NULL,
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `employer_health_plan`
        DROP COLUMN `benefits_payer_id`,
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )
