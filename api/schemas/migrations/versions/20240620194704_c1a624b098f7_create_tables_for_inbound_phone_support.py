"""create_tables_for_inbound_phone_support

Revision ID: c1a624b098f7
Revises: 30920966ae58
Create Date: 2024-06-20 19:47:04.565005+00:00

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "c1a624b098f7"
down_revision = "30920966ae58"
branch_labels = None
depends_on = None


def upgrade():
    # Create table 'inbound_phone_number'
    op.create_table(
        "inbound_phone_number",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("number", sa.VARCHAR(20), nullable=False),
    )

    # Create table 'org_inbound_phone_number'
    op.create_table(
        "org_inbound_phone_number",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "org_id", sa.Integer, sa.ForeignKey("organization.id"), nullable=False
        ),
        sa.Column(
            "inbound_phone_number_id",
            sa.Integer,
            sa.ForeignKey("inbound_phone_number.id"),
            nullable=False,
        ),
    )

    # Create the unique constraint on the org_id column
    op.create_unique_constraint(
        "uq_org_inbound_phone_number_org_id", "org_inbound_phone_number", ["org_id"]
    )


def downgrade():
    # Drop the unique constraint on the org_id column
    op.drop_constraint(
        "uq_org_inbound_phone_number_org_id", "org_inbound_phone_number", type_="unique"
    )

    # Drop 'org_inbound_phone_number' table
    op.drop_table("org_inbound_phone_number")

    # Drop 'inbound_phone_number' table
    op.drop_table("inbound_phone_number")
