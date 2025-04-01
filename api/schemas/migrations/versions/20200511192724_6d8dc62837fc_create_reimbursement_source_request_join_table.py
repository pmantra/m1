"""create reimbursement source/request join table

Revision ID: 6d8dc62837fc
Revises: 24d70cff6a3d
Create Date: 2020-05-11 19:27:24.501947

"""
from alembic import op
import sqlalchemy as sa
from storage.connection import db


# revision identifiers, used by Alembic.
revision = "6d8dc62837fc"
down_revision = "24d70cff6a3d"
branch_labels = None
depends_on = None


def upgrade():
    # 1. Create the join table
    # 2. Insert values into the join table using the existing column
    # 3. Allow the old column to be nullable (so that it doesn't cause errors in new code)
    op.create_table(
        "reimbursement_request_source_requests",
        sa.Column(
            "reimbursement_request_id",
            sa.BigInteger,
            sa.ForeignKey("reimbursement_request.id"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "reimbursement_request_source_id",
            sa.BigInteger,
            sa.ForeignKey("reimbursement_request_source.id"),
            primary_key=True,
            nullable=False,
        ),
    )

    db.session.execute(
        """
INSERT INTO reimbursement_request_source_requests
    (reimbursement_request_id, reimbursement_request_source_id)
SELECT r.id AS reimbursement_request_id, r.reimbursement_request_source_id
FROM reimbursement_request r;"""
    )
    db.session.commit()

    op.drop_constraint(
        "reimbursement_request_ibfk_2", "reimbursement_request", type_="foreignkey"
    )
    op.alter_column(
        "reimbursement_request",
        "reimbursement_request_source_id",
        nullable=True,
        existing_type=sa.BigInteger,
    )


def downgrade():
    # 1. Restore nullable=False and the foreign key constraint
    # 2. Drop join table
    op.alter_column(
        "reimbursement_request",
        "reimbursement_request_source_id",
        nullable=False,
        existing_type=sa.BigInteger,
    )
    op.create_foreign_key(
        "reimbursement_request_ibfk_2",
        "reimbursement_request",
        "reimbursement_request_source",
        ["reimbursement_request_source_id"],
        ["id"],
    )

    op.drop_table("reimbursement_request_source_requests")
