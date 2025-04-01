"""Add slug column on need table

Revision ID: 7783ec40c780
Revises: ab02eff69511
Create Date: 2024-03-15 17:34:41.672968+00:00

"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "7783ec40c780"
down_revision = "e5bca3bff1fc"
branch_labels = None
depends_on = None


def upgrade():
    sql = """
        ALTER TABLE `need`
        ADD COLUMN `slug` varchar(128) DEFAULT NULL,
        ADD UNIQUE KEY `slug_uq_1` (`slug`),
        ALGORITHM=INPLACE,
        LOCK=NONE;
    """
    op.execute(sql)


def downgrade():
    sql = """
        ALTER TABLE `need`
        DROP COLUMN `slug`,
        DROP KEY `slug_uq_1`,
        ALGORITHM=INPLACE,
        LOCK=NONE;
    """
    op.execute(sql)
