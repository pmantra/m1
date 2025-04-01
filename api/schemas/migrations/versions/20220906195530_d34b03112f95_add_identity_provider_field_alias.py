"""add_identity_provider_field_alias

Revision ID: d34b03112f95
Revises: cfc06fe7e76e
Create Date: 2022-09-06 19:55:30.794951+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "d34b03112f95"
down_revision = "cfc06fe7e76e"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS `identity_provider_field_alias` (
            id BIGINT PRIMARY KEY NOT NULL AUTO_INCREMENT,
            field VARCHAR(64) NOT NULL,
            alias VARCHAR(64) NOT NULL,
            identity_provider_id BIGINT NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            modified_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP 
                ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (identity_provider_id) 
                REFERENCES `identity_provider`(`id`) 
                ON DELETE CASCADE,
            INDEX ix_user_external_identity_field_alias_field (field),
            INDEX ix_user_external_identity_field_alias_alias (alias),
            INDEX ix_user_external_identity_field_alias_identity_provider_id 
                (identity_provider_id),
            UNIQUE (identity_provider_id, field)
        );
        """
    )
    pass


def downgrade():
    op.execute("DROP TABLE IF EXISTS `identity_provider_field_alias` CASCADE;")
