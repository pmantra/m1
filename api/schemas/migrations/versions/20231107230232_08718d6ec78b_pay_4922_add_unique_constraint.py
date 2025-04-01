"""PAY-4922-add-unique-constraint

Revision ID: 08718d6ec78b
Revises: 0003f27a5541
Create Date: 2023-11-07 23:02:32.553564+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "08718d6ec78b"
down_revision = "0003f27a5541"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "ALTER TABLE `health_plan_year_to_date_spend` ADD UNIQUE (`transmission_id`)"
    )


def downgrade():
    op.execute(
        "ALTER TABLE `health_plan_year_to_date_spend` DROP INDEX `transmission_id`"
    )
