"""update member_health_plan with patient relationship

Revision ID: 77869680cc2c
Revises: d94763010316
Create Date: 2023-10-03 19:39:31.225890+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "77869680cc2c"
down_revision = "065ef13b21fe"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `member_health_plan`
        ADD COLUMN `patient_sex` enum('MALE','FEMALE','UNKNOWN'),
        ADD COLUMN `patient_relationship` enum('SPOUSE','CHILD','DOMESTIC_PARTNER','FORMER_SPOUSE','OTHER'),
        ALGORITHM=INPLACE, LOCK=NONE; 
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `member_health_plan`
        DROP COLUMN `patient_sex`,
        DROP COLUMN `patient_relationship`,
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )
