"""Move reimbursement account type to its own table

Revision ID: 345c984723e6
Revises: 0b8316ce0ab9
Create Date: 2021-09-01 17:55:15.847553+00:00

"""
from alembic import op
import sqlalchemy as sa


from wallet.models.constants import AlegeusAccountType

# revision identifiers, used by Alembic.
revision = "345c984723e6"
down_revision = "0b8316ce0ab9"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "reimbursement_account_type",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("alegeus_account_type", sa.VARCHAR(4), nullable=True),
    )

    op.add_column(
        "reimbursement_account",
        sa.Column("alegeus_flex_account_key", sa.VARCHAR(50), nullable=True),
    )

    op.add_column(
        "reimbursement_account",
        sa.Column(
            "alegeus_account_type_id",
            sa.BigInteger,
            sa.ForeignKey("reimbursement_account_type.id"),
        ),
    )

    op.drop_column("reimbursement_account", "alegeus_account_type")


def downgrade():
    op.drop_column("reimbursement_account", "alegeus_flex_account_key")
    op.add_column(
        "reimbursement_account",
        sa.Column("alegeus_account_type", sa.Enum(AlegeusAccountType), nullable=True),
    )

    op.drop_constraint(
        "reimbursement_account_ibfk_3", "reimbursement_account", type_="foreignkey"
    )
    op.drop_column("reimbursement_account", "alegeus_account_type_id")
    op.drop_table("reimbursement_account_type")
