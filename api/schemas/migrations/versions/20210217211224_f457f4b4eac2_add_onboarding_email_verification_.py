"""Add onboarding_email_verification_enabled to org

Revision ID: f457f4b4eac2
Revises: 170fea4ffb7f
Create Date: 2021-02-17 21:12:24.565294

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f457f4b4eac2"
down_revision = "170fea4ffb7f"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "organization",
        sa.Column(
            "onboarding_email_verification_enabled",
            sa.Boolean,
            server_default=sa.sql.expression.false(),
            nullable=False,
        ),
    )


def downgrade():
    op.drop_column("organization", "onboarding_email_verification_enabled")
