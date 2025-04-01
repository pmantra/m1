"""add_reimbursement_request_person

Revision ID: 59bc3491147b
Revises: 0a3d3275a24c
Create Date: 2024-02-05 15:41:25.981416+00:00

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "59bc3491147b"
down_revision = "0a3d3275a24c"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE reimbursement_request
        ADD COLUMN person_receiving_service_id int(11) DEFAULT NULL,
        ADD COLUMN person_receiving_service_member_status ENUM('MEMBER','NON_MEMBER') DEFAULT NULL,
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE reimbursement_request
        DROP COLUMN person_receiving_service_id,
        DROP COLUMN person_receiving_service_member_status,
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )
