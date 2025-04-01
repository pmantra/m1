"""add_key_e9y_member_id_credit

Revision ID: 5633c8e96d92
Revises: 9e03148ee623
Create Date: 2024-09-04 00:52:04.527010+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "5633c8e96d92"
down_revision = "9e03148ee623"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE credit 
        ADD KEY `idx_eligibility_member_id` (`eligibility_member_id`),
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE credit 
        DROP KEY `idx_eligibility_member_id`,
        ALGORITHM=INPLACE,
        LOCK=NONE;
            """
    )
