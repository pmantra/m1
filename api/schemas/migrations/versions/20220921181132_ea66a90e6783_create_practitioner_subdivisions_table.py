"""Create practitioner_subdivisions table

Revision ID: ea66a90e6783
Revises: 5e05b875fe54
Create Date: 2022-09-21 18:11:32.900418+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "ea66a90e6783"
down_revision = "5e05b875fe54"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "practitioner_subdivisions",
        sa.Column(
            "user_id",
            sa.Integer,
            sa.ForeignKey("practitioner_profile.user_id"),
            nullable=False,
        ),
        sa.Column("subdivision_code", sa.String(6), nullable=True),
    )
    op.create_unique_constraint(
        constraint_name="uq_practitioner_subdivision",
        table_name="practitioner_subdivisions",
        columns=["user_id", "subdivision_code"],
    )


def downgrade():
    op.drop_table("practitioner_subdivisions")
