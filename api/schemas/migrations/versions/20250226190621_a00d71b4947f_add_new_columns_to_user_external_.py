"""add new columns to user_external_identity

Revision ID: a00d71b4947f
Revises: a6ba16430be6
Create Date: 2025-02-26 19:06:21.688908+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "a00d71b4947f"
down_revision = "a6ba16430be6"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE user_external_identity
        ADD COLUMN sso_email varchar(128) DEFAULT NULL,
        ADD COLUMN auth0_user_id varchar(128) DEFAULT NULL,
        ADD COLUMN sso_user_first_name varchar(128) DEFAULT NULL,
        ADD COLUMN sso_user_last_name varchar(128) DEFAULT NULL,
        ADD UNIQUE INDEX `idx_auth0_user_id` (`auth0_user_id`),
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE user_external_identity
        DROP INDEX `idx_auth0_user_id`,
        DROP COLUMN sso_email,
        DROP COLUMN auth0_user_id,
        DROP COLUMN sso_user_first_name,
        DROP COLUMN sso_user_last_name,
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )
