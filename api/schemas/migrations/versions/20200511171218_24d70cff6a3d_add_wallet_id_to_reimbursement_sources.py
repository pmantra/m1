"""add wallet id to reimbursement sources

Revision ID: 24d70cff6a3d
Revises: 6283041ec8b7
Create Date: 2020-05-11 17:12:18.507046

"""
from alembic import op
import sqlalchemy as sa
from storage.connection import db


# revision identifiers, used by Alembic.
revision = "24d70cff6a3d"
down_revision = "6283041ec8b7"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "reimbursement_request_source",
        sa.Column(
            "reimbursement_wallet_id",
            sa.BigInteger,
            sa.ForeignKey(
                "reimbursement_wallet.id",
                name="reimbursement_request_source_wallet_id_fk",
            ),
            nullable=True,
        ),
    )

    # Set reimbursement_wallet_id using each source's user_asset
    db.session.execute(
        """
UPDATE reimbursement_request_source s
LEFT JOIN user_asset_message am ON am.user_asset_id = s.user_asset_id
LEFT JOIN message m ON m.id = am.message_id
LEFT JOIN reimbursement_wallet w ON w.channel_id = m.channel_id
SET s.reimbursement_wallet_id = w.id;
    """
    )
    db.session.commit()


def downgrade():
    op.drop_constraint(
        "reimbursement_request_source_wallet_id_fk",
        "reimbursement_request_source",
        type_="foreignkey",
    )
    op.drop_column("reimbursement_request_source", "reimbursement_wallet_id")
