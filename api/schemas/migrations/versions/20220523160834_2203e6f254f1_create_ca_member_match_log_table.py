"""create ca member match log table

Revision ID: 2203e6f254f1
Revises: 6ce33b3384c4
Create Date: 2022-05-23 16:08:34.719871+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "2203e6f254f1"
down_revision = "9bcb08116083"
branch_labels = None
depends_on = None


def upgrade():
    # Duplicate user data captured here due to infrastructure not set up in big query
    # Once big query migrates to new infra, can drop following columns: country, org, track, user flags
    op.create_table(
        "ca_member_match_log",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("user.id"), nullable=False),
        sa.Column(
            "care_advocate_id", sa.Integer, sa.ForeignKey("user.id"), nullable=False
        ),
        sa.Column(
            "organization_id",
            sa.Integer,
            sa.ForeignKey("organization.id"),
            nullable=True,
        ),
        sa.Column("track", sa.String(120), nullable=True),
        sa.Column("user_flag_ids", sa.String(255), nullable=True),
        sa.Column("attempts", sa.Integer, nullable=False),
        sa.Column("matched_at", sa.DateTime, nullable=False),
    )


def downgrade():
    op.drop_table("ca_member_match_log")
