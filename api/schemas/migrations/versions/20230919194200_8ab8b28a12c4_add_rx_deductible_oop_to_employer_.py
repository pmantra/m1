"""add rx deductible oop to employer health plan table

Revision ID: 8ab8b28a12c4
Revises: 90c0ec2f1e9c
Create Date: 2023-09-19 19:42:00.156781+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "8ab8b28a12c4"
down_revision = "90c0ec2f1e9c"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `employer_health_plan`
        ADD COLUMN `rx_fam_oop_max_limit` int(11) DEFAULT NULL after `fam_oop_max_limit`,
        ADD COLUMN `rx_fam_deductible_limit` int(11) DEFAULT NULL after `fam_oop_max_limit`,
        ADD COLUMN `rx_ind_oop_max_limit` int(11) DEFAULT NULL after `fam_oop_max_limit`,
        ADD COLUMN `rx_ind_deductible_limit` int(11) DEFAULT NULL after `fam_oop_max_limit`,
        ADD COLUMN `rx_integrated` tinyint(1) NOT NULL DEFAULT 1 after `fam_oop_max_limit`,
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `employer_health_plan`
        DROP COLUMN `rx_integrated`,
        DROP COLUMN `rx_ind_deductible_limit`,
        DROP COLUMN `rx_ind_oop_max_limit`,
        DROP COLUMN `rx_fam_deductible_limit`,
        DROP COLUMN `rx_fam_oop_max_limit`,
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )
