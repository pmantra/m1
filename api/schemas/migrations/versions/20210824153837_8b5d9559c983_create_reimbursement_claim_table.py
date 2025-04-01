"""Create reimbursement_claim table

Revision ID: 8b5d9559c983
Revises: c48fe6aab255
Create Date: 2021-08-24 15:38:37.800133+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "8b5d9559c983"
down_revision = "c48fe6aab255"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "reimbursement_claim",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column(
            "reimbursement_request_id",
            sa.BigInteger,
            sa.ForeignKey("reimbursement_request.id"),
        ),
        sa.Column("alegeus_claim_id", sa.VARCHAR(50), nullable=True),
        sa.Column("amount", sa.Numeric(scale=2), nullable=True),
        sa.Column("status", sa.VARCHAR(15), nullable=True),
    )
    op.create_unique_constraint(
        "alegeus_claim_id", "reimbursement_claim", ["alegeus_claim_id"]
    )


def downgrade():
    op.drop_constraint("alegeus_claim_id", "reimbursement_claim", type_="unique")
    op.drop_table("reimbursement_claim")
