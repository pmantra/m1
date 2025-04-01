"""add_contract_type_index_practitioner_contract

Revision ID: cc954a6ef115
Revises: c046f39d48aa
Create Date: 2023-06-29 19:19:34.811061+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "cc954a6ef115"
down_revision = "c046f39d48aa"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `practitioner_contract`
            ADD INDEX `idx_contract_type` 
                (contract_type), 
            ALGORITHM=INPLACE, LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """ 
        ALTER TABLE `practitioner_contract` 
            DROP INDEX `idx_contract_type`, 
            ALGORITHM=INPLACE, LOCK=NONE;
        """
    )
