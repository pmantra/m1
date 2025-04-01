"""Cascade reimbursement_wallet_users user

Revision ID: be50b083d542
Revises: 4848a3069f08
Create Date: 2023-08-14 19:33:27.257332+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "be50b083d542"
down_revision = "4848a3069f08"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint(
        "reimbursement_wallet_users_ibfk_2", "reimbursement_wallet_users", "foreignkey"
    )
    user_constraint_query = """
        ALTER TABLE `reimbursement_wallet_users`
        ADD CONSTRAINT `reimbursement_wallet_users_ibfk_2`
        FOREIGN KEY (`user_id`) REFERENCES `user` (`id`)
        ON DELETE CASCADE
        """
    op.execute(user_constraint_query)


def downgrade():
    op.drop_constraint(
        "reimbursement_wallet_users_ibfk_2", "reimbursement_wallet_users", "foreignkey"
    )
    user_constraint_query = """
        ALTER TABLE `reimbursement_wallet_users`
        ADD CONSTRAINT `reimbursement_wallet_users_ibfk_2`
        FOREIGN KEY (`user_id`) REFERENCES `user` (`id`)
        """
    op.execute(user_constraint_query)
