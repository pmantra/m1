"""update_reimbursement_taxation_status_enum

Revision ID: 1fde6e015df6
Revises: 7632237e43f0
Create Date: 2023-02-15 18:16:48.193854+00:00

"""
from alembic import op
import sqlalchemy as sa
import enum


# revision identifiers, used by Alembic.
revision = "1fde6e015df6"
down_revision = "719f4770bfd3"
branch_labels = None
depends_on = None


class OldTaxationStatus(enum.Enum):
    QUALIFIED = "QUALIFIED"
    NON_QUALIFIED = "NON_QUALIFIED"


class NewTaxationStatus(enum.Enum):
    QUALIFIED = "QUALIFIED"
    NON_QUALIFIED = "NON_QUALIFIED"
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
