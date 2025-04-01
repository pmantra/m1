"""change_payer_name_to_string

Revision ID: b0c16254f55c
Revises: b4fc98a5fe8f
Create Date: 2024-10-15 13:07:45.316894+00:00

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "b0c16254f55c"
down_revision = "b4fc98a5fe8f"
branch_labels = None
depends_on = None


def upgrade():
    sql = """
            ALTER TABLE `payer_list`
            CHANGE COLUMN `payer_name` `payer_name` varchar(50) NOT NULL,
            ALGORITHM=COPY, LOCK=SHARED;
        """
    op.execute(sql)


def downgrade():
    sql = """
            ALTER TABLE `payer_list`
            CHANGE COLUMN `payer_name` `payer_name` enum('UHC','Cigna','ESI','OHIO_HEALTH','AETNA','BLUE_EXCHANGE','ANTHEM') NOT NULL,
            ALGORITHM=COPY, LOCK=SHARED;
        """
    op.execute(sql)
