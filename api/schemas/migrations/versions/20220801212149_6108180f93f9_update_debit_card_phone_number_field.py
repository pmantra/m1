"""Update debit card phone number field

Revision ID: 6108180f93f9
Revises: 11b89d66ce63
Create Date: 2022-08-01 21:21:49.985638+00:00

"""
from alembic import op
import sqlalchemy as sa

from wallet.models.reimbursement_wallet_debit_card import ReimbursementWalletDebitCard

# revision identifiers, used by Alembic.
revision = "6108180f93f9"
down_revision = "11b89d66ce63"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        ReimbursementWalletDebitCard.__tablename__,
        "phone_number",
        existing_type=sa.String(255),
        nullable=True,
    )


def downgrade():
    op.alter_column(
        ReimbursementWalletDebitCard.__tablename__,
        "phone_number",
        existing_type=sa.String(255),
        nullable=False,
    )
