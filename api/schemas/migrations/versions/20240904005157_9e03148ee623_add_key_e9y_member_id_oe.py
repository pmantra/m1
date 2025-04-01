"""add_key_e9y_member_id_oe

Revision ID: 9e03148ee623
Revises: bb6463398c4a
Create Date: 2024-09-04 00:51:57.245872+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "9e03148ee623"
down_revision = "bb6463398c4a"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE organization_employee 
        DROP KEY `idx_eligibility_member_id`,
        ALGORITHM=INPLACE,
        LOCK=NONE;
        ALTER TABLE organization_employee 
        ADD KEY `idx_eligibility_member_id` (`eligibility_member_id`),
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE organization_employee 
        DROP KEY `idx_eligibility_member_id`,
        ALGORITHM=INPLACE,
        LOCK=NONE;
            """
    )
