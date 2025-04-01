"""BEX-4511_2.8_altering_direct_payment_invoice

Revision ID: 9a1c75534a06
Revises: b3c335dce625
Create Date: 2024-09-04 18:51:59.914359+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "9a1c75534a06"
down_revision = "b3c335dce625"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
    ALTER TABLE direct_payment_invoice
    CHANGE voided_by_id voided_by_user_id BIGINT NULL COMMENT 'User_id that voided the record (if the record was voided, unenforced by db)',
    CHANGE generated_report_json report_generated_json MEDIUMTEXT NULL COMMENT 'The generated report stored in JSON format (unenforced by db)',
    ADD bill_allocated_by_user_id BIGINT NULL COMMENT 'User id that allocated the bills (if allocation was via admin, unenforced by db)';
    """
    )


def downgrade():
    op.execute(
        """
    ALTER TABLE direct_payment_invoice
    CHANGE voided_by_user_id voided_by_id BIGINT NULL COMMENT 'User_id that voided the record (if the record was voided, unenforced by db)',
    CHANGE report_generated_json generated_report_json TEXT NULL COMMENT 'The generated report stored in JSON format (unenforced by db)',
    DROP COLUMN bill_allocated_by_user_id;
    """
    )
