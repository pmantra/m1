"""add_e9y_member_id_oe

Revision ID: 7f8d9f740fee
Revises: d3434301cca3
Create Date: 2024-09-03 23:51:24.735434+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "7f8d9f740fee"
down_revision = "d3434301cca3"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE organization_employee ADD COLUMN new_eligibility_member_id BIGINT,
        ADD UNIQUE KEY `uq_new_eligibility_member_id` (`new_eligibility_member_id`),
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
            ALTER TABLE organization_employee DROP COLUMN new_eligibility_member_id,
            DROP KEY `uq_new_eligibility_member_id`,
            ALGORITHM=INPLACE,
            LOCK=NONE;
            """
    )
