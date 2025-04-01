"""alter_excluded_procedures_primary_key

Revision ID: 995a741a1d45
Revises: c6a3c6796445
Create Date: 2023-09-12 21:07:16.278800+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "995a741a1d45"
down_revision = "c6a3c6796445"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `maven`.`reimbursement_organization_settings_excluded_procedures`
            DROP PRIMARY KEY,
            ADD COLUMN id BIGINT AUTO_INCREMENT PRIMARY KEY,
            ADD CONSTRAINT uidx_organization_settings_excluded_procedure UNIQUE (
                reimbursement_organization_settings_id, global_procedure_id
            ),
            ALGORITHM=INPLACE, LOCK=SHARED
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `maven`.`reimbursement_organization_settings_excluded_procedures`
            DROP PRIMARY KEY,
            DROP COLUMN id,
            DROP KEY uidx_organization_settings_excluded_procedure,
            ADD CONSTRAINT pk_organization_settings_excluded_procedure PRIMARY KEY (
                reimbursement_organization_settings_id, global_procedure_id
            ),
            ALGORITHM=INPLACE, LOCK=NONE 
        """
    )
