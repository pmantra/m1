"""Add unique accumulation id

Revision ID: 1981613f7c66
Revises: 873b5f882e66
Create Date: 2024-10-04 21:56:43.769345+00:00

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "1981613f7c66"
down_revision = "a996e25565d4"
branch_labels = None
depends_on = None


def upgrade():
    sql = """
    ALTER TABLE `accumulation_treatment_mapping`
    ADD `accumulation_unique_id` VARCHAR(128)  NULL  DEFAULT NULL AFTER `id`,
    ADD UNIQUE INDEX `idx_accumulation_unique_id` (`accumulation_unique_id`),
    ALGORITHM=INPLACE, LOCK=NONE;
    """
    op.execute(sql)


def downgrade():
    sql = """
    ALTER TABLE `accumulation_treatment_mapping` DROP `accumulation_unique_id`,
    ALGORITHM=INPLACE, LOCK=NONE;
    """
    op.execute(sql)
