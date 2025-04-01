"""Cascade reimbursement_wallet_users

Revision ID: 48f06e0e92dd
Revises: 7575498b9710
Create Date: 2023-08-10 17:27:39.858806+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "48f06e0e92dd"
down_revision = "7575498b9710"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint(
        "reimbursement_wallet_users_ibfk_1", "reimbursement_wallet_users", "foreignkey"
    )
    wallet_constraint_query = """
        ALTER TABLE `reimbursement_wallet_users`
        ADD CONSTRAINT `reimbursement_wallet_users_ibfk_1`
        FOREIGN KEY (`reimbursement_wallet_id`) REFERENCES `reimbursement_wallet` (`id`)
        ON DELETE CASCADE
        """
    op.execute(wallet_constraint_query)


def downgrade():
    op.drop_constraint(
        "reimbursement_wallet_users_ibfk_1", "reimbursement_wallet_users", "foreignkey"
    )
    wallet_constraint_query = """
        ALTER TABLE `reimbursement_wallet_users`
        ADD CONSTRAINT `reimbursement_wallet_users_ibfk_1`
        FOREIGN KEY (`reimbursement_wallet_id`) REFERENCES `reimbursement_wallet` (`id`)
        """
    op.execute(wallet_constraint_query)
