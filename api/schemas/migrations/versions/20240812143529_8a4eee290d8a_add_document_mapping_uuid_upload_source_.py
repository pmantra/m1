"""add_document_mapping_uuid_upload_source_to_reimbursement_request_source

Revision ID: 8a4eee290d8a
Revises: de3e402ab15a
Create Date: 2024-08-12 14:35:29.031969+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "8a4eee290d8a"
down_revision = "de3e402ab15a"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `reimbursement_request_source`
        ADD COLUMN `document_mapping_uuid` varchar(36) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
        ADD COLUMN `upload_source` enum('INITIAL_SUBMISSION','POST_SUBMISSION', 'ADMIN') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `reimbursement_request_source`
        DROP COLUMN `document_mapping_uuid`,
        DROP COLUMN `upload_source`,
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )
