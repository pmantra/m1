"""global_search_provider_data

Revision ID: 85994049c25d
Revises: 5be3550ee05a
Create Date: 2025-01-10 17:41:34.503462+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "85994049c25d"
down_revision = "5be3550ee05a"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "practitioner_data",
        sa.Column("user_id", sa.Integer, sa.ForeignKey("user.id"), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.current_timestamp(),
            comment="The time at which this record was created.",
        ),
        sa.Column("practitioner_profile_json", sa.Text, nullable=True),
        sa.Column("practitioner_profile_modified_at", sa.DateTime, nullable=True),
        sa.Column("need_json", sa.Text, nullable=True),
        sa.Column("need_modified_at", sa.DateTime, nullable=True),
        sa.Column("vertical_json", sa.Text, nullable=True),
        sa.Column("vertical_modified_at", sa.DateTime, nullable=True),
        sa.Column("specialty_json", sa.Text, nullable=True),
        sa.Column("specialty_modified_at", sa.DateTime, nullable=True),
    )


def downgrade():
    op.drop_table("practitioner_data")
