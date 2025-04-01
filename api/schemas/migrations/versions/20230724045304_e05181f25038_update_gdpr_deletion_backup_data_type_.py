"""update-gdpr-deletion-backup-data-type-to-longtext

Revision ID: e05181f25038
Revises: e6f81ff574bc
Create Date: 2023-07-24 04:53:04.663743+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "e05181f25038"
down_revision = "40d684548a12"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE gdpr_deletion_backup MODIFY data LONGTEXT")


def downgrade():
    op.execute("ALTER TABLE gdpr_deletion_backup MODIFY data TEXT")
