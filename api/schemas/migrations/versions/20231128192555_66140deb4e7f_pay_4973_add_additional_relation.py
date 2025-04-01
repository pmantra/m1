"""PAY-4973-add-additional-relation

Revision ID: 66140deb4e7f
Revises: 849be3d99d61
Create Date: 2023-11-28 19:25:55.205800+00:00

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "66140deb4e7f"
down_revision = "849be3d99d61"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `member_health_plan` CHANGE `patient_relationship` `patient_relationship` ENUM('CARDHOLDER','SPOUSE','CHILD','DOMESTIC_PARTNER','FORMER_SPOUSE','OTHER', 'STUDENT', 'DISABLED_DEPENDENT', 'ADULT_DEPENDENT')
    
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `member_health_plan` CHANGE `patient_relationship` `patient_relationship` ENUM('CARDHOLDER','SPOUSE','CHILD','DOMESTIC_PARTNER','FORMER_SPOUSE','OTHER')
        """
    )
