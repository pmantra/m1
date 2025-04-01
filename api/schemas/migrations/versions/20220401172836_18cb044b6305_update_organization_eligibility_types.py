"""Update Organization eligibility types

Revision ID: 18cb044b6305
Revises: 5b01394a497e
Create Date: 2022-04-01 17:28:36.131787+00:00

"""
import enum

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "18cb044b6305"
down_revision = "5b01394a497e"
branch_labels = None
depends_on = None


class OldOrganizationEligibilityType(enum.Enum):
    STANDARD = "STANDARD"
    ALTERNATE = "ALTERNATE"
    FILELESS = "FILELESS"
    CLIENT_SPECIFIC = "CLIENT_SPECIFIC"
    SAML = "SAML"
    HEALTHPLAN = "HEALTHPLAN"


class NewOrganizationEligibilityType(enum.Enum):
    STANDARD = "STANDARD"
    ALTERNATE = "ALTERNATE"
    FILELESS = "FILELESS"
    CLIENT_SPECIFIC = "CLIENT_SPECIFIC"
    SAML = "SAML"
    HEALTHPLAN = "HEALTHPLAN"
    UNKNOWN = "UNKNOWN"


def upgrade():
    op.alter_column(
        "organization",
        "eligibility_type",
        type_=sa.Enum(NewOrganizationEligibilityType),
        existing_type=sa.Enum(OldOrganizationEligibilityType),
        nullable=True,
    )


def downgrade():
    op.alter_column(
        "organization",
        "eligibility_type",
        type_=sa.Enum(OldOrganizationEligibilityType),
        existing_type=sa.Enum(NewOrganizationEligibilityType),
        nullable=True,
    )
