"""create_processing_record

Revision ID: a9802687a488
Revises: e05181f25038
Create Date: 2023-07-25 02:30:45.931322+00:00

"""
from storage.connection import db


# revision identifiers, used by Alembic.
revision = "a9802687a488"
down_revision = "e05181f25038"
branch_labels = None
depends_on = None


def upgrade():
    query = """
    CREATE TABLE `bill_processing_record` (
    id bigint(20) NOT NULL AUTO_INCREMENT,
    bill_id bigint(20) NOT NULL,
    transaction_id varchar(36) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    processing_record_type varchar(100) NOT NULL,
    bill_status varchar(100) NOT NULL,
    body text NOT NULL,
   `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
    # indexes
    PRIMARY KEY (`id`),
    KEY `ix_bill_id` (`bill_id`),
    KEY `ix_transaction_id` (`transaction_id`),
    # If a bill is deleted for GDPR reasons, definitely also remove all attached records
    CONSTRAINT `bill_id_ibfk_1` FOREIGN KEY (`bill_id`) REFERENCES `bill` (`id`) ON DELETE CASCADE
    );
    """
    db.session.execute(query)
    db.session.commit()


def downgrade():
    query = "DROP TABLE IF EXISTS `bill_processing_record`;"
    db.session.execute(query)
    db.session.commit()
