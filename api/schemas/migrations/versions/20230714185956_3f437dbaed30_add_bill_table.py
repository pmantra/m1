"""add-bill-table

Revision ID: 3f437dbaed30
Revises: a2e30796ff8a
Create Date: 2023-07-14 18:59:56.135289+00:00

"""
from storage.connection import db


# revision identifiers, used by Alembic.
revision = "3f437dbaed30"
down_revision = "a2e30796ff8a"
branch_labels = None
depends_on = None


def upgrade():
    query = """
    CREATE TABLE `bill` (
    id bigint(20) NOT NULL AUTO_INCREMENT,
    uuid varchar(36) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    amount int DEFAULT 0,
    label text DEFAULT NULL,
    payor_type enum('MEMBER', 'EMPLOYER', 'CLINIC') COLLATE utf8mb4_unicode_ci NOT NULL,
    payor_id bigint(20) NOT NULL,
    procedure_id bigint(20) NOT NULL,
    payment_method enum('DIRECT_PAYMENTS', 'WRITE_OFF', 'OFFLINE') default 'DIRECT_PAYMENTS',
    payment_method_label text DEFAULT NULL,
    status enum('NEW', 'PROCESSING', 'PAID', 'FAILED', 'REFUNDED', 'CANCELLED') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'NEW',
    error_type text DEFAULT null,
    reimbursement_request_created_at  datetime DEFAULT NULL,
    # default fields
   `modified_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
   `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
    # state tracking fields
    processing_at  datetime DEFAULT NULL,
    paid_at  datetime DEFAULT NULL,
    refund_initiated_at datetime DEFAULT NULL,
    refunded_at  datetime DEFAULT NULL,
    failed_at  datetime DEFAULT NULL,
    cancelled_at  datetime DEFAULT NULL,
    # indexes
    PRIMARY KEY (`id`),
    KEY `ix_payor_type_payor_id_details` (`payor_type`,`payor_id`),
    KEY `ix_procedure_id` (`procedure_id`),
    KEY `ix_status` (`status`)
    );
    """
    db.session.execute(query)
    db.session.commit()


def downgrade():
    query = "DROP TABLE IF EXISTS `bill`;"
    db.session.execute(query)
    db.session.commit()
