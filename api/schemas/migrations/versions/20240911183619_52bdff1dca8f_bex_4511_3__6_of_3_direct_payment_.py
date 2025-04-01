"""BEX-4511_3__6_of_3_direct_payment_invoice_bill_allocation

Revision ID: 52bdff1dca8f
Revises: 2c2e13efccb8
Create Date: 2024-09-11 18:36:19.974185+00:00

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "52bdff1dca8f"
down_revision = "2c2e13efccb8"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
            CREATE TABLE direct_payment_invoice_bill_allocation (
                id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT 'Unique internal id',
                uuid CHAR(36) COLLATE utf8mb4_unicode_ci NOT NULL UNIQUE COMMENT 'Unique external id (UUID4)',
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'The time at which this record was created',
                created_by_process ENUM('ADMIN', 'INVOICE_GENERATOR') NOT NULL DEFAULT 'INVOICE_GENERATOR' COMMENT 'One of: ADMIN, INVOICE_GENERATOR',
                created_by_user_id BIGINT(20) DEFAULT NULL COMMENT 'User id that created the row(if creation was via admin, unenforced by db)',
                direct_payment_invoice_id BIGINT NOT NULL COMMENT 'invoice internal id',
                bill_uuid CHAR(36) NOT NULL UNIQUE COMMENT 'Bill external id (UUID4). Unique - cannot appear more than once in the table. Specifically restricted from having a foreign key relationship with the bill table for future Billing Triforce Migration',
                KEY idx_direct_payment_invoice_id (direct_payment_invoice_id),
                KEY idx_direct_payment_invoice_bill_allocation_uuid (uuid),
                CONSTRAINT fk_direct_payment_invoice_id FOREIGN KEY (direct_payment_invoice_id) REFERENCES direct_payment_invoice(id) ON DELETE CASCADE
            ) COMMENT 'Table that maps bills to invoices.';
        """
    )


def downgrade():
    op.execute("""DROP TABLE IF EXISTS direct_payment_invoice_bill_allocation;""")
