"""Set auto_increment value for benefit id

Revision ID: 77d9ef7f6f41
Revises: ec9249d78841
Create Date: 2023-01-31 20:07:18.891515+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "77d9ef7f6f41"
down_revision = "ec9249d78841"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE `reimbursement_wallet_benefit` AUTO_INCREMENT = 101")


def downgrade():
    pass
