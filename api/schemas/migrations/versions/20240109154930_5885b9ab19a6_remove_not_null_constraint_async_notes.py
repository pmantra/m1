"""remove_not_null_constraint_async_notes

Revision ID: 5885b9ab19a6
Revises: 6b607e7b6e42
Create Date: 2024-01-09 15:49:30.522700+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "5885b9ab19a6"
down_revision = "6b607e7b6e42"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `async_encounter_summary`
        MODIFY COLUMN `provider_id` int(11);
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `async_encounter_summary`
        MODIFY COLUMN `provider_id` int(11) NOT NULL;
        """
    )
