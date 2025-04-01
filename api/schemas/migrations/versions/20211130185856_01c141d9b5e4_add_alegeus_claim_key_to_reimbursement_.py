"""add alegeus_claim_key to reimbursement_claim

Revision ID: 01c141d9b5e4
Revises: 9915422ca717
Create Date: 2021-11-30 18:58:56.483219+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "01c141d9b5e4"
down_revision = "9915422ca717"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "reimbursement_claim",
        sa.Column("alegeus_claim_key", sa.BigInteger, default=None),
    )


def downgrade():
    op.drop_column("reimbursement_claim", "alegeus_claim_key")
