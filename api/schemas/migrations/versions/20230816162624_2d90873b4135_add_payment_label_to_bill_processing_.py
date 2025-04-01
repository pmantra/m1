"""add-payment-label-to-bill-processing-record

Revision ID: 2d90873b4135
Revises: 0b5bc784a6a3
Create Date: 2023-08-16 16:26:24.665238+00:00

"""
from storage.connection import db


# revision identifiers, used by Alembic.
revision = "2d90873b4135"
down_revision = "0b5bc784a6a3"
branch_labels = None
depends_on = None


def upgrade():
    query = """
    ALTER TABLE `bill_processing_record`
    ADD COLUMN `payment_method_label` text COLLATE utf8mb4_unicode_ci AFTER `bill_status`,
    LOCK=NONE;
    """
    db.session.execute(query)
    db.session.commit()


def downgrade():
    query = """
     ALTER TABLE `bill_processing_record`
     DROP COLUMN `payment_method_label`;
    """
    db.session.execute(query)
    db.session.commit()
