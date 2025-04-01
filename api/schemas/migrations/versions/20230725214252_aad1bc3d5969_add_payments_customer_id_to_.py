"""Add payments customer id to reimbursement org

Revision ID: aad1bc3d5969
Revises: a9802687a488
Create Date: 2023-07-25 21:42:52.395950+00:00

"""
from storage.connection import db


# revision identifiers, used by Alembic.
revision = "aad1bc3d5969"
down_revision = "a9802687a488"
branch_labels = None
depends_on = None


def upgrade():
    query = """
    ALTER TABLE `reimbursement_organization_settings` ADD COLUMN `payments_customer_id` CHAR(36), ALGORITHM=INPLACE, LOCK=NONE;
    """
    db.session.execute(query)
    db.session.commit()


def downgrade():
    query = """
    ALTER TABLE `reimbursement_organization_settings` DROP COLUMN `payments_customer_id`, ALGORITHM=INPLACE, LOCK=NONE;
    """
    db.session.execute(query)
    db.session.commit()
