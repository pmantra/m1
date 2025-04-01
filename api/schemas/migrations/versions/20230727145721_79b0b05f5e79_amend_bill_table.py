"""amend-bill-table

Revision ID: 79b0b05f5e79
Revises: aad1bc3d5969
Create Date: 2023-07-27 14:57:21.199409+00:00

"""
from storage.connection import db


# revision identifiers, used by Alembic.
revision = "79b0b05f5e79"
down_revision = "aad1bc3d5969"
branch_labels = None
depends_on = None


def upgrade():
    query = """
     ALTER TABLE `bill`
     ADD COLUMN `cost_breakdown_id` bigint(20) DEFAULT NULL AFTER `procedure_id`,
     ADD COLUMN `display_date` varchar(50) DEFAULT 'created_at',
     ADD COLUMN `last_calculated_fee` int DEFAULT 0,
     CHANGE COLUMN `payment_method` `payment_method` enum('PAYMENT_GATEWAY','WRITE_OFF','OFFLINE') COLLATE utf8mb4_unicode_ci DEFAULT 'PAYMENT_GATEWAY'
     ;
     """
    db.session.execute(query)
    db.session.commit()


def downgrade():
    query = """
     ALTER TABLE `bill`
     DROP COLUMN `cost_breakdown_id`,
     DROP COLUMN `display_date`,
     DROP COLUMN `last_calculated_fee`,
     CHANGE COLUMN `payment_method` `payment_method` enum('DIRECT_PAYMENTS','WRITE_OFF','OFFLINE') COLLATE utf8mb4_unicode_ci DEFAULT 'DIRECT_PAYMENTS',
     ;
     """
    db.session.execute(query)
    db.session.commit()
