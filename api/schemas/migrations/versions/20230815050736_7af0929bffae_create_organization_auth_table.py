"""create organization auth table

Revision ID: 7af0929bffae
Revises: fd4f906b9db5
Create Date: 2023-08-15 05:07:36.361311+00:00

"""
from storage.connection import db

# revision identifiers, used by Alembic.
revision = "7af0929bffae"
down_revision = "fd4f906b9db5"
branch_labels = None
depends_on = None


def upgrade():
    query = """
    CREATE TABLE `organization_auth` (
      `id` int(11) NOT NULL AUTO_INCREMENT,
      `organization_id` int(11) NOT NULL,
      `mfa_required` tinyint(1) DEFAULT '0',
      `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
      `modified_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
      PRIMARY KEY (`id`),
      UNIQUE KEY `ix_organization_auth_organization_id` (`organization_id`)
    );
    """
    db.session.execute(query)
    db.session.commit()


def downgrade():
    query = """
    DROP TABLE IF EXISTS `organization_auth`;
    """
    db.session.execute(query)
    db.session.commit()
