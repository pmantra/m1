"""survey-url-optional-on-ros

Revision ID: 1b0bbe1e61cf
Revises: 728886422392
Create Date: 2025-02-04 20:11:51.737555+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "1b0bbe1e61cf"
down_revision = "728886422392"
branch_labels = None
depends_on = None


def upgrade():
    sql = """
            ALTER TABLE `reimbursement_organization_settings`
            MODIFY COLUMN `survey_url` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
            ALGORITHM=COPY, LOCK=SHARED;
        """
    op.execute(sql)


def downgrade():
    sql = """
            ALTER TABLE `reimbursement_organization_settings`
            MODIFY COLUMN `survey_url` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
            ALGORITHM=COPY, LOCK=SHARED;
        """
    op.execute(sql)
