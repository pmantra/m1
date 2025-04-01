"""Add id to practitioner_subdivisions table

Revision ID: bee4ba5684b5
Revises: ea66a90e6783
Create Date: 2022-09-22 18:33:37.069678+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "bee4ba5684b5"
down_revision = "ea66a90e6783"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_table("practitioner_subdivisions")

    op.create_table(
        "practitioner_subdivisions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "practitioner_id",
            sa.Integer,
            sa.ForeignKey("practitioner_profile.user_id"),
            nullable=False,
        ),
        sa.Column("subdivision_code", sa.String(6), nullable=True),
    )
    op.create_unique_constraint(
        constraint_name="uq_practitioner_subdivision",
        table_name="practitioner_subdivisions",
        columns=["practitioner_id", "subdivision_code"],
    )


def downgrade():
    op.drop_table("practitioner_subdivisions")

    op.create_table(
        "practitioner_subdivisions",
        sa.Column(
            "practitioner_id",
            sa.Integer,
            sa.ForeignKey("practitioner_profile.user_id"),
            nullable=False,
        ),
        sa.Column("subdivision_code", sa.String(6), nullable=True),
    )
    op.create_unique_constraint(
        constraint_name="uq_practitioner_subdivision",
        table_name="practitioner_subdivisions",
        columns=["practitioner_id", "subdivision_code"],
    )
