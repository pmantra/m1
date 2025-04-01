"""BEX-4511_2.5_direct_payment_invoice

Revision ID: d3434301cca3
Revises: 172679aff5c9
Create Date: 2024-09-03 18:32:34.300578+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "d3434301cca3"
down_revision = "172679aff5c9"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE direct_payment_invoice (
        id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT 'Unique internal id',
        uuid VARCHAR(36)  COLLATE utf8mb4_unicode_ci NOT NULL UNIQUE COMMENT 'Unique external id (UUID4)',
        created_by_process ENUM('ADMIN', 'INVOICE_GENERATOR') NOT NULL COMMENT 'The process that created the invoice.',
        created_by_user_id BIGINT DEFAULT NULL COMMENT 'User id that created the record (if creation was via admin, unenforced by db)',
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'The time at which this record was created. (UTC)',
        reimbursement_organization_settings_id BIGINT NOT NULL COMMENT 'ID of the reimbursement organisation settings.',
        bill_creation_cutoff_start_at DATETIME NOT NULL COMMENT 'Start time (inclusive) of the bill sweep-in time window. (UTC)',
        bill_creation_cutoff_end_at DATETIME NOT NULL COMMENT 'End time (inclusive) of the bill sweep-in time window. (UTC)',
        bills_allocated_at DATETIME DEFAULT NULL COMMENT 'The time at which bills were allocated to this invoice.',
        bills_allocated_by_process ENUM('ADMIN', 'INVOICE_GENERATOR') DEFAULT NULL COMMENT 'The process that allocated bills to the invoice.',
        voided_at DATETIME DEFAULT NULL COMMENT 'The time at which this invoice was voided.(UTC). Used for soft delete.',
        voided_by_id BIGINT DEFAULT NULL COMMENT 'User_id that voided the record (if the record was voided, unenforced by db)',
        report_generated_at DATETIME DEFAULT NULL COMMENT 'The time at which the report was generated. UTC',
        generated_report_json TEXT DEFAULT NULL COMMENT 'The generated report stored in JSON format (unenforced by db)',

        INDEX ix_uuid (uuid),
        INDEX ix_reimbursement_organization_settings_id (reimbursement_organization_settings_id),
        INDEX ix_bill_creation_cutoff_start_at (bill_creation_cutoff_start_at),
        INDEX ix_bill_creation_cutoff_end_at (bill_creation_cutoff_end_at),               
        FOREIGN KEY fk_reimbursement_organization_settings_id (reimbursement_organization_settings_id) REFERENCES reimbursement_organization_settings (id)
        );
        """
    )


def downgrade():
    op.execute("""DROP TABLE IF EXISTS direct_payment_invoice;""")
