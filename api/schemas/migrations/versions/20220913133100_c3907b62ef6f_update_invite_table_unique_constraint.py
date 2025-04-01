"""Update invite table unique constraint

Revision ID: c3907b62ef6f
Revises: 80f6621df164
Create Date: 2022-09-13 13:31:00.349351+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "c3907b62ef6f"
down_revision = "80f6621df164"
branch_labels = None
depends_on = None


def upgrade():
    # Modify column length
    op.execute(
        "ALTER TABLE `invite` MODIFY COLUMN `type` VARCHAR(120) NOT NULL DEFAULT 'PARTNER'"
    )

    # Add new constraint
    op.execute(
        "ALTER TABLE `invite` ADD UNIQUE `uq_user_type` (`created_by_user_id`, `type`)"
    )

    # Drop old constraint
    op.execute("ALTER TABLE `invite` DROP INDEX `created_by_user_id`")


def downgrade():
    # Add old constraint
    op.execute("ALTER TABLE `invite` ADD UNIQUE (`created_by_user_id`)")

    # Drop new constraint
    op.execute("ALTER TABLE `invite` DROP INDEX `uq_user_type`")

    # Modify column length
    op.execute(
        "ALTER TABLE `invite` MODIFY COLUMN `type` VARCHAR(255) NOT NULL DEFAULT 'PARTNER'"
    )
