"""Add eligibility-logic to email domains

Revision ID: 656b2e03d223
Revises: 03c83a319162
Create Date: 2021-02-26 18:42:09.310595

"""
from alembic import op
import sqlalchemy as sa
import enum


# revision identifiers, used by Alembic.
revision = "656b2e03d223"
down_revision = "03c83a319162"
branch_labels = None
depends_on = None


def upgrade():
    class EmailEligibilityLogic(enum.Enum):
        CLIENT_SPECIFIC = "CLIENT_SPECIFIC"
        FILELESS = "FILELESS"

    op.drop_column("organization", "onboarding_email_verification_enabled")
    op.add_column(
        "organization_email_domain",
        sa.Column(
            "eligibility_logic",
            sa.Enum(EmailEligibilityLogic),
            nullable=False,
            default=EmailEligibilityLogic.CLIENT_SPECIFIC,
        ),
    )


def downgrade():
    op.add_column(
        "organization",
        sa.Column(
            "onboarding_email_verification_enabled",
            sa.Boolean,
            server_default=sa.sql.expression.false(),
            nullable=False,
        ),
    )
    op.drop_column("organization_email_domain", "eligibility_logic")
