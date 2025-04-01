"""client_track_alter_unique_key

Revision ID: f6322f22eb2c
Revises: 0933f3939eb3
Create Date: 2023-12-06 04:02:49.282722+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "f6322f22eb2c"
down_revision = "0933f3939eb3"
branch_labels = None
depends_on = None


def upgrade():

    op.execute(
        """
        ALTER TABLE `client_track`
        DROP INDEX `uc_client_track_organization_track`,
        ADD UNIQUE `uc_client_track_organization_track`(`organization_id`,`track`,`length_in_days`,`active`),
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )


def downgrade():

    op.execute(
        """
        ALTER TABLE `client_track`
        DROP INDEX `uc_client_track_organization_track`,
        ADD UNIQUE `uc_client_track_organization_track`(`organization_id`,`track`),
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )
