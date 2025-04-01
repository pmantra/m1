"""Add Direct Payments consent table

Revision ID: 7c390b7cf4ec
Revises: 1088e6a98f3d
Create Date: 2023-08-04 18:53:28.297382+00:00

"""
from storage.connection import db


# revision identifiers, used by Alembic.
revision = "7c390b7cf4ec"
down_revision = "1088e6a98f3d"
branch_labels = None
depends_on = None


def upgrade():
    query = """
    CREATE TABLE `reimbursement_wallet_billing_consent` (
    `id` bigint(20) NOT NULL AUTO_INCREMENT,
    `reimbursement_wallet_id` BIGINT(20) NOT NULL,
    `version` SMALLINT(6) NOT NULL,
    `action` ENUM('CONSENT', 'REVOKE') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'CONSENT',
    `acting_user_id` INT(11) NOT NULL,
    `ip_address` VARCHAR(39) NULL,
    `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
    `modified_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `ix_reimbusement_wallet_id_version_status` (`reimbursement_wallet_id`, `version`, `action`),
    KEY `ix_version_status` (`version`, `action`)
    );
    """
    db.session.execute(query)
    db.session.commit()


def downgrade():
    query = "DROP TABLE IF EXISTS `reimbursement_wallet_billing_consent`;"
    db.session.execute(query)
    db.session.commit()
