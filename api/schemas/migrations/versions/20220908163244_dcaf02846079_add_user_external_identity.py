"""add_user_external_identity

Revision ID: dcaf02846079
Revises: 3c8e19bfe944
Create Date: 2022-09-08 16:32:44.824573+00:00

"""
import pathlib
from alembic import op


# revision identifiers, used by Alembic.
revision = "dcaf02846079"
down_revision = "204aba110c60"
branch_labels = None
depends_on = None


def upgrade():
    current_file = pathlib.Path(__file__).resolve()
    sql_file = current_file.parent / f"{current_file.stem}.sql"
    migration = sql_file.read_text()
    # SQLAlchemy tries to parse the `;` and provides no way to override this.
    #   So we are splitting each delimited statement and executing individually...
    # Discard the initial `DELIMITER` statement.
    parts = migration.split("$$")[1:]
    connection = op.get_bind()
    with connection.begin():
        for sql in parts:
            connection.execute(sql)


def downgrade():
    op.execute(
        """
        DROP TABLE IF EXISTS `user_external_identity` CASCADE;
        DROP TRIGGER IF EXISTS `after_external_identity_insert`;
        DROP TRIGGER IF EXISTS `after_external_identity_update`;
        DROP TRIGGER IF EXISTS `after_external_identity_delete`;
        DROP TRIGGER IF EXISTS `before_external_identity_insert`;
        DROP TRIGGER IF EXISTS `before_org_external_id_insert`;
        DROP TRIGGER IF EXISTS `before_external_identity_update`;
        DROP TRIGGER IF EXISTS `before_org_external_id_update`;
        DROP PROCEDURE IF EXISTS `lookupIDPForOrganization`;
        DROP PROCEDURE IF EXISTS `lookupOrgExternalIDForIdentity`;
        DROP PROCEDURE IF EXISTS `fillIdentityProviders`;
        DROP PROCEDURE IF EXISTS `copyExternalIdentities`;
        DROP PROCEDURE IF EXISTS `copyExternalIdentity`;
        """
    )
