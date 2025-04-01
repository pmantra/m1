"""reimbursement_wallet drop column channel_id

Revision ID: 4823d7b719ed
Revises: f7171bfed449
Create Date: 2024-03-12 04:31:27.085919+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "4823d7b719ed"
down_revision = "f7171bfed449"
branch_labels = None
depends_on = None


def upgrade():
    stmt = """
    ALTER TABLE `reimbursement_wallet` DROP FOREIGN KEY `reimbursement_wallet_ibfk_4`;
    
    ALTER TABLE `reimbursement_wallet` DROP INDEX `reimbursement_wallet_ibfk_4`;
    
    ALTER TABLE `reimbursement_wallet` DROP COLUMN channel_id;
    """
    op.execute(stmt)


def downgrade():
    stmt = """
    ALTER TABLE `reimbursement_wallet` ADD COLUMN `channel_id` INT(11) DEFAULT NULL; 
    
    
    ALTER TABLE `reimbursement_wallet` 
    ADD INDEX `reimbursement_wallet_ibfk_4` (`channel_id`);
    
    ALTER TABLE `reimbursement_wallet` 
    ADD CONSTRAINT `reimbursement_wallet_ibfk_4` 
    FOREIGN KEY (`channel_id`) REFERENCES `channel` (`id`);
    """
    op.execute(stmt)
