"""update-patient-relationship-column-in-member-health-plan-table

Revision ID: 48e68c854773
Revises: d21ddd63347b
Create Date: 2023-11-13 17:56:10.571017+00:00

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "48e68c854773"
down_revision = "d21ddd63347b"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `member_health_plan`
        MODIFY COLUMN `patient_relationship` enum('CARDHOLDER','SPOUSE','CHILD','DOMESTIC_PARTNER','FORMER_SPOUSE','OTHER'),
        ALGORITHM=COPY, LOCK=SHARED;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `member_health_plan`
        MODIFY COLUMN `patient_relationship` enum('SPOUSE','CHILD','DOMESTIC_PARTNER','FORMER_SPOUSE','OTHER'),
        ALGORITHM=COPY, LOCK=SHARED;
        """
    )
