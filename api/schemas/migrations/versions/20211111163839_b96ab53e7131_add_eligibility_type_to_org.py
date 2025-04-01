"""add eligibility type to org

Revision ID: b96ab53e7131
Revises: 189578402bdb
Create Date: 2021-11-11 16:38:39.588447+00:00

"""
from alembic import op
import sqlalchemy as sa
from models.enterprise import OrganizationEligibilityType

# revision identifiers, used by Alembic.
revision = "b96ab53e7131"
down_revision = "01c141d9b5e4"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "organization",
        sa.Column(
            "eligibility_type",
            sa.Enum(OrganizationEligibilityType),
            default=OrganizationEligibilityType.STANDARD,
            nullable=False,
        ),
    )


def downgrade():
    op.drop_column("organization", "eligibility_type")
