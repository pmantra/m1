"""allow-list-rbac-table

Revision ID: 849be3d99d61
Revises: 253210d523cc
Create Date: 2023-11-28 20:11:45.359248+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "849be3d99d61"
down_revision = "253210d523cc"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE `allowed_list` (
            `is_rbac_allowed` bool DEFAULT false,
            `view_name` varchar(50) NOT NULL,
            PRIMARY KEY (`view_name`)
        );
        CREATE INDEX `allowed_list_view_name` ON allowed_list(view_name);
    """
    )


def downgrade():
    op.execute(
        """
        DROP INDEX `allowed_list_view_name` ON `allowed_list`;
        DROP TABLE IF EXISTS `allowed_list`;
        """
    )
