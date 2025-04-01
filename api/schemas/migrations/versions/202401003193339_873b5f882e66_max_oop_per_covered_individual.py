"""max_oop_per_covered_individual

Revision ID: 873b5f882e66
Revises: 3775547b3c48
Create Date: 2024-10-03 19:33:39.817515+00:00

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "873b5f882e66"
down_revision = "3775547b3c48"
branch_labels = None
depends_on = None


def upgrade():
    sql = """
    ALTER TABLE `employer_health_plan`
    ADD COLUMN max_oop_per_covered_individual INTEGER DEFAULT NULL after fam_oop_max_limit,
    ALGORITHM=COPY;
    """
    op.execute(sql)


def downgrade():
    sql = """
    ALTER TABLE `employer_health_plan`
    DROP COLUMN max_oop_per_covered_individual,
    ALGORITHM=COPY;
    """
    op.execute(sql)
