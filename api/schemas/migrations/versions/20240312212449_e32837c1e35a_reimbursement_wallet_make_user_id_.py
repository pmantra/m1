"""reimbursement_wallet make user_id nullable

Revision ID: e32837c1e35a
Revises: 4823d7b719ed
Create Date: 2024-03-12 21:24:49.249258+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "e32837c1e35a"
down_revision = "4823d7b719ed"
branch_labels = None
depends_on = None


def upgrade():
    stmt = """
        ALTER TABLE `reimbursement_wallet` MODIFY user_id INT(11) DEFAULT NULL;
    """
    op.execute(stmt)


def downgrade():
    stmt = """
        -- Must not have any foreign key constraints prior to modifying the column.
        -- Hence we must remove the foreign key constraint, modify the column type,
        -- then replace the foreign key constraint.
        ALTER TABLE `reimbursement_wallet` DROP FOREIGN KEY `reimbursement_wallet_ibfk_1`;
    
        ALTER TABLE `reimbursement_wallet` MODIFY user_id INT(11) NOT NULL;

        ALTER TABLE `reimbursement_wallet` ADD CONSTRAINT `reimbursement_wallet_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`);
    """
    op.execute(stmt)
