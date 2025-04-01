"""BEX-1514-4_of_n_annual_insurance_questionnaire_response

Revision ID: 253210d523cc
Revises: 961875048a2b
Create Date: 2023-11-28 16:33:16.448950+00:00

"""
from storage.connection import db

# revision identifiers, used by Alembic.
revision = "253210d523cc"
down_revision = "6bd2273378af"
branch_labels = None
depends_on = None


def upgrade():
    query = """
    CREATE TABLE `annual_insurance_questionnaire_response` (
      `id` bigint(20) NOT NULL AUTO_INCREMENT,
      `uuid` varchar(36) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
      `wallet_id` bigint(20) NOT NULL,
      `questionnaire_id` varchar(256) COLLATE utf8mb4_unicode_ci NOT NULL,
      `user_response_json` text COLLATE utf8mb4_unicode_ci NOT NULL,
      `submitting_user_id` bigint(11) NOT NULL,
      `alegus_synch_datetime` datetime DEFAULT NULL,
      `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
      `modified_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
      PRIMARY KEY (`id`),
      KEY `ix_uuid` (`uuid`),
      KEY `ix_wallet_id` (`wallet_id`)
    );
    """
    db.session.execute(query)
    db.session.commit()


def downgrade():
    query = "DROP TABLE IF EXISTS `annual_insurance_questionnaire_response`;"
    db.session.execute(query)
    db.session.commit()
