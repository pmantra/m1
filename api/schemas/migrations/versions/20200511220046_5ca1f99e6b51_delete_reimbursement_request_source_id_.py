"""delete reimbursement_request.source_id column

Revision ID: 5ca1f99e6b51
Revises: 6d8dc62837fc
Create Date: 2020-05-11 22:00:46.005244

"""
from alembic import op
import sqlalchemy as sa
from storage.connection import db


# revision identifiers, used by Alembic.
revision = "5ca1f99e6b51"
down_revision = "6d8dc62837fc"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_column("reimbursement_request", "reimbursement_request_source_id")


def downgrade():
    # 1. Create the source_id column
    # 2. Set the values of source_id using join table
    op.add_column(
        "reimbursement_request",
        sa.Column("reimbursement_request_source_id", sa.BigInteger, nullable=True),
    )

    db.session.execute(
        """
UPDATE reimbursement_request r
JOIN reimbursement_request_source_requests sr ON sr.reimbursement_request_id = r.id
SET r.reimbursement_request_source_id = sr.reimbursement_request_source_id;"""
    )
    db.session.commit()
