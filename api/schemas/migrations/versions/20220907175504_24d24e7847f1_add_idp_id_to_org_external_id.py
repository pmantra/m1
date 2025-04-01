"""add_idp_id_to_org_external_id

Revision ID: 24d24e7847f1
Revises: d34b03112f95
Create Date: 2022-09-07 17:55:04.228390+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "24d24e7847f1"
down_revision = "d34b03112f95"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `organization_external_id`
            DROP INDEX `idp_external_id`,
            ADD UNIQUE INDEX `uidx_identity_provider_external_id` 
                (identity_provider_id, external_id),
            ADD UNIQUE INDEX `uidx_data_provider_external_id`
                (data_provider_organization_id, external_id);
        UPDATE `organization_external_id` oei
            JOIN identity_provider idp 
                ON oei.idp = idp.name
        SET oei.identity_provider_id = coalesce(idp.id, 0)
        WHERE oei.idp IS NOT NULL;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `organization_external_id`
            DROP INDEX `uidx_identity_provider_external_id`,
            DROP INDEX `uidx_data_provider_external_id`,
            ADD UNIQUE INDEX `idp_external_id` (`idp`,`external_id`)
        """
    )
