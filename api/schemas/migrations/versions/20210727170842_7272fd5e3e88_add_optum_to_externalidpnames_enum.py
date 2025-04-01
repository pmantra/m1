"""add optum to ExternalIDPNames enum

Revision ID: 7272fd5e3e88
Revises: 0055cdc21010
Create Date: 2021-07-27 17:08:42.312389+00:00

"""
from alembic import op
import sqlalchemy as sa
import enum


# revision identifiers, used by Alembic.
revision = "7272fd5e3e88"
down_revision = "0055cdc21010"
branch_labels = None
depends_on = None


class OldExternalIDPNames(enum.Enum):
    VIRGIN_PULSE = "VIRGIN_PULSE"
    OKTA = "OKTA"
    CASTLIGHT = "CASTLIGHT"


class NewExternalIDPNames(enum.Enum):
    VIRGIN_PULSE = "VIRGIN_PULSE"
    OKTA = "OKTA"
    CASTLIGHT = "CASTLIGHT"
    OPTUM = "OPTUM"


def upgrade():
    op.alter_column(
        "organization_external_id",
        "idp",
        type_=sa.Enum(NewExternalIDPNames),
        existing_type=sa.Enum(OldExternalIDPNames),
        nullable=False,
    )


def downgrade():
    op.alter_column(
        "organization_external_id",
        "idp",
        type_=sa.Enum(OldExternalIDPNames),
        existing_type=sa.Enum(NewExternalIDPNames),
        nullable=False,
    )
