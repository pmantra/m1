"""mirror_report_config_tables

Revision ID: b6c13ae367ae
Revises: a27b7dd7443c
Create Date: 2024-04-11 13:53:34.865777+00:00

"""
import pathlib

from alembic import op


# revision identifiers, used by Alembic.
revision = "b6c13ae367ae"
down_revision = "a27b7dd7443c"
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
        DROP TRIGGER IF EXISTS `after_wallet_client_report_configuration_insert`;
        DROP TRIGGER IF EXISTS `after_wallet_client_report_configuration_update`;
        DROP TRIGGER IF EXISTS `after_wallet_client_report_configuration_delete`;
        DROP TRIGGER IF EXISTS `after_wallet_client_report_configuration_report_columns_insert`;
        DROP TRIGGER IF EXISTS `after_wallet_client_report_configuration_report_columns_update`;
        DROP TRIGGER IF EXISTS `after_wallet_client_report_configuration_report_columns_delete`;
        DELETE FROM `wallet_client_report_configuration_report_columns_v2`;
        DELETE FROM `wallet_client_report_configuration_v2`;
        UPDATE `wallet_client_reports` report
        SET report.configuration_id = null;
        """
    )
