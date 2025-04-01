"""Credit card enabled bool to reimburse org setting model

Revision ID: 11b89d66ce63
Revises: 3c2902191655
Create Date: 2022-07-29 22:24:11.945507+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "11b89d66ce63"
down_revision = "3c2902191655"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "reimbursement_organization_settings",
        sa.Column(
            "debit_card_enabled",
            sa.Boolean,
            nullable=False,
            default=False,
        ),
    )


def downgrade():
    op.drop_column("reimbursement_organization_settings", "debit_card_enabled")
