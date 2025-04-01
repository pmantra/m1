"""[sc-98195] adds an id to availability_request_member_times

Revision ID: 4318fa20a399
Revises: b612b4a82fda
Create Date: 2022-07-14 19:11:35.320134+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "4318fa20a399"
down_revision = "b612b4a82fda"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "ALTER TABLE availability_request_member_times ADD COLUMN id INTEGER NOT NULL PRIMARY KEY AUTO_INCREMENT"
    )


def downgrade():
    op.drop_column("availability_request_member_times", "id")
