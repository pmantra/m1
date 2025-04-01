"""Add user_onboarding_state table

Revision ID: 285553f32120
Revises: 656b2e03d223
Create Date: 2021-03-08 23:25:26.369554

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "285553f32120"
down_revision = "656b2e03d223"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "user_onboarding_state",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "user_id", sa.Integer, sa.ForeignKey("user.id"), nullable=False, unique=True
        ),
        sa.Column("state", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime),
        sa.Column("modified_at", sa.DateTime),
    )


def downgrade():
    op.drop_table("user_onboarding_state")
