"""up the character limit on reimburement_claim.status

Revision ID: 9915422ca717
Revises: e5de7affd119
Create Date: 2021-11-19 19:11:37.388915+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "9915422ca717"
down_revision = "e5de7affd119"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "reimbursement_claim",
        "status",
        existing_type=sa.VARCHAR(15),
        type_=sa.VARCHAR(50),
        nullable=True,
    )


def downgrade():
    op.alter_column(
        "reimbursement_claim",
        "status",
        existing_type=sa.VARCHAR(50),
        type_=sa.VARCHAR(15),
        nullable=True,
    )
