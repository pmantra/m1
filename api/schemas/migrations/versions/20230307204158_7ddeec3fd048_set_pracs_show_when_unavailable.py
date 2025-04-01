"""set-pracs-show-when-unavailable

Revision ID: 7ddeec3fd048
Revises: a666e7598712
Create Date: 2023-03-07 20:41:58.583229+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "7ddeec3fd048"
down_revision = "a666e7598712"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("UPDATE practitioner_profile SET show_when_unavailable=FALSE")


def downgrade():
    pass
