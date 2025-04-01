"""Add external_identity table

Revision ID: 5a4b928fa285
Revises: 864747f2d111
Create Date: 2020-02-19 15:34:03.079073

"""
from alembic import op
import sqlalchemy as sa
import snowflake


# revision identifiers, used by Alembic.
revision = "5a4b928fa285"
down_revision = "864747f2d111"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "external_identity",
        sa.Column(
            "id",
            sa.BIGINT,
            primary_key=True,
            autoincrement=False,
            default=snowflake.generate,
        ),
        sa.Column("idp", sa.String(120), nullable=False),
        sa.Column("external_user_id", sa.String(120), nullable=False),
        sa.Column("rewards_id", sa.String(120), unique=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("user.id"), nullable=False),
        sa.Column(
            "organization_employee_id",
            sa.Integer,
            sa.ForeignKey("organization_employee.id"),
            nullable=True,
        ),
    )
    op.create_unique_constraint(
        "external_identity_uq_1", "external_identity", ["idp", "external_user_id"]
    )


def downgrade():
    op.drop_table("external_identity")
