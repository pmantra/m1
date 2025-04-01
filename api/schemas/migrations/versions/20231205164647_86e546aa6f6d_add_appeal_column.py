"""Add appeal column

Revision ID: 86e546aa6f6d
Revises: 43ba0f1dfa02
Create Date: 2023-12-05 16:46:47.633049+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "86e546aa6f6d"
down_revision = "43ba0f1dfa02"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `reimbursement_request`
        ADD COLUMN `appeal_of` bigint(20) DEFAULT NULL,
        ADD UNIQUE KEY `appeal_of` (`appeal_of`),
        ADD CONSTRAINT `reimbursement_request_ibfk_4` FOREIGN KEY (`appeal_of`) REFERENCES `reimbursement_request` (`id`),
        ALGORITHM=COPY, LOCK=SHARED;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `reimbursement_request`
        DROP COLUMN `appeal_of`,
        DROP KEY `appeal_of`,
        DROP FOREIGN KEY `reimbursement_request_ibfk_4`,
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )
