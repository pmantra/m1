"""rename_e9y_member_id_mt

Revision ID: b1788111d309
Revises: 18bcb694ce57
Create Date: 2024-09-04 00:30:07.136263+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "b1788111d309"
down_revision = "18bcb694ce57"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE member_track 
        CHANGE COLUMN `eligibility_member_id` `eligibility_member_id_deleted` INT,
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE member_track 
        CHANGE COLUMN `eligibility_member_id_deleted` `eligibility_member_id` INT,
        ALGORITHM=INPLACE,
        LOCK=NONE;
            """
    )
