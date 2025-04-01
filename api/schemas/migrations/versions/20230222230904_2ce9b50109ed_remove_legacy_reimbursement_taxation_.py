"""remove_legacy_reimbursement_taxation_status

Revision ID: 2ce9b50109ed
Revises: 0c254f82e4af
Create Date: 2023-02-22 23:09:04.805068+00:00

"""
from alembic import op
import sqlalchemy as sa
import enum


# revision identifiers, used by Alembic.
revision = "2ce9b50109ed"
down_revision = "0c254f82e4af"
branch_labels = None
depends_on = None


class OldTaxationStatus(enum.Enum):
    QUALIFIED = "QUALIFIED"
    NON_QUALIFIED = "NON_QUALIFIED"
    TAXABLE = "TAXABLE"
    NON_TAXABLE = "NON_TAXABLE"
    ADOPTION_QUALIFIED = "ADOPTION_QUALIFIED"
    ADOPTION_NON_QUALIFIED = "ADOPTION_NON_QUALIFIED"


class NewTaxationStatus(enum.Enum):
    TAXABLE = "TAXABLE"
    NON_TAXABLE = "NON_TAXABLE"
    ADOPTION_QUALIFIED = "ADOPTION_QUALIFIED"
    ADOPTION_NON_QUALIFIED = "ADOPTION_NON_QUALIFIED"


def upgrade():
    op.alter_column(
        "reimbursement_wallet",
        "taxation_status",
        type_=sa.Enum(NewTaxationStatus),
        existing_type=sa.Enum(OldTaxationStatus),
        nullable=True,
    )

    op.alter_column(
        "reimbursement_organization_settings",
        "taxation_status",
        type_=sa.Enum(NewTaxationStatus),
        existing_type=sa.Enum(OldTaxationStatus),
        nullable=True,
    )

    op.alter_column(
        "reimbursement_request",
        "taxation_status",
        type_=sa.Enum(NewTaxationStatus),
        existing_type=sa.Enum(OldTaxationStatus),
        nullable=True,
    )


def downgrade():
    op.alter_column(
        "reimbursement_wallet",
        "taxation_status",
        type_=sa.Enum(OldTaxationStatus),
        existing_type=sa.Enum(NewTaxationStatus),
        nullable=True,
    )

    op.alter_column(
        "reimbursement_organization_settings",
        "taxation_status",
        type_=sa.Enum(OldTaxationStatus),
        existing_type=sa.Enum(NewTaxationStatus),
        nullable=True,
    )

    op.alter_column(
        "reimbursement_request",
        "taxation_status",
        type_=sa.Enum(OldTaxationStatus),
        existing_type=sa.Enum(NewTaxationStatus),
        nullable=True,
    )
