"""Add organization_type enum field

Revision ID: 654e34b39c96
Revises: 6eab6c579d30
Create Date: 2021-04-29 20:10:41.889142+00:00

This migration adds an organization.internal_type field which was requested
by the Data team in Clubhouse story ch36002 to help them differentiate between
"real" and test, demo/VIP, and Maven-4-Maven organizations in BigQuery.
It is NOT intended for use in application code to determine product behavior.

"""
import enum

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "654e34b39c96"
down_revision = "6eab6c579d30"
branch_labels = None
depends_on = None


class OrganizationType(enum.Enum):
    REAL = "REAL"
    TEST = "TEST"
    DEMO_OR_VIP = "DEMO_OR_VIP"
    MAVEN_FOR_MAVEN = "MAVEN_FOR_MAVEN"


def upgrade():
    op.add_column(
        "organization",
        sa.Column(
            "internal_type",
            sa.Enum(OrganizationType),
            nullable=False,
            default=OrganizationType.REAL,
        ),
    )


def downgrade():
    op.drop_column("organization", "internal_type")
