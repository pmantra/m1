"""BEX-4511_1.2_of_3_organization_invoicing_settings

Revision ID: 4b9f72e66092
Revises: fb4f2099a9a4
Create Date: 2024-08-22 20:08:14.173501+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "4b9f72e66092"
down_revision = "f487a7f170b0"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS organization_invoicing_settings (
          id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT 'Unique internal id.',
          uuid VARCHAR(36) COLLATE utf8mb4_unicode_ci NOT NULL UNIQUE COMMENT 'Unique external id. UUID4 format.',
          created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'The time at which this record was created.',
          updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'The time at which this record was updated.',
          organization_id INT NOT NULL COMMENT 'ID of the org.',
          created_by_user_id INT NOT NULL COMMENT 'user_id that created the record',
          updated_by_user_id INT NOT NULL COMMENT 'user_id that updated the record',          
          invoicing_active_at DATETIME NULL COMMENT 'The date at which the employer activated invoice based billing.',
          invoice_cadence VARCHAR(13)  COLLATE utf8mb4_unicode_ci  NULL COMMENT 'Invoice generation cadence in CRON format. application will ignore hh mm.',
          bill_processing_delay_days TINYINT UNSIGNED NOT NULL DEFAULT 14 COMMENT 'Bills will be processed bill_processing_delay_days after bill creation.',
          bill_cutoff_at_buffer_days TINYINT UNSIGNED NOT NULL DEFAULT 2 COMMENT 'The cutoff offset in days from the current date for the latest bill creation date. ',
          KEY idx_uuid (uuid),
          KEY idx_organization_id (organization_id),
          CONSTRAINT fk_organization_id FOREIGN KEY (organization_id) REFERENCES organization(id) ON DELETE  CASCADE 
        );"""
    )


def downgrade():
    op.execute("""DROP TABLE IF EXISTS `organization_invoicing_settings`;""")
