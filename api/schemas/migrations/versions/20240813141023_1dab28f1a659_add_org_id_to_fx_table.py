"""add_org_id_to_fx_table

Revision ID: 1dab28f1a659
Revises: e74b7a0584e3
Create Date: 2024-08-13 14:10:23.663951+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "1dab28f1a659"
down_revision = "e74b7a0584e3"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `reimbursement_request_exchange_rates`
        ADD COLUMN `organization_id` int(11) DEFAULT NULL,
        ADD INDEX `organization_id_idx` (`organization_id`),
        ADD FOREIGN KEY (`organization_id`) REFERENCES `organization` (`id`) ON DELETE CASCADE,
        ALGORITHM=COPY,
        LOCK=SHARED;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `reimbursement_request_exchange_rates`
        DROP FOREIGN KEY `reimbursement_request_exchange_rates_ibfk_1`,
        DROP INDEX `organization_id_idx`,
        DROP COLUMN `organization_id`,
        ALGORITHM=COPY, LOCK=SHARED;
        """
    )
