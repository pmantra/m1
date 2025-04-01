"""drop-constraint-member-track-ibfk-5-in-member-track

Revision ID: e28b272f602e
Revises: 9a3153569852
Create Date: 2023-07-12 17:30:00.864768+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "e28b272f602e"
down_revision = "9a3153569852"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "ALTER TABLE member_track "
        "DROP FOREIGN KEY member_track_ibfk_5, "
        "ALGORITHM=INPLACE, LOCK=NONE"
    )


def downgrade():
    op.execute(
        "ALTER TABLE member_track "
        "ADD CONSTRAINT member_track_ibfk_5 "
        "FOREIGN KEY (legacy_module_id) REFERENCES module(id)"
    )
