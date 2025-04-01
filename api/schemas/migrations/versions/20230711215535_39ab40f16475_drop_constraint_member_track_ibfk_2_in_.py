"""drop-constraint-member-track-ibfk-2-in-member-track

Revision ID: 39ab40f16475
Revises: 2b829f95ca5c
Create Date: 2023-07-11 21:55:35.993717+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "39ab40f16475"
down_revision = "b0b86604b18f"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "ALTER TABLE member_track "
        "DROP FOREIGN KEY member_track_ibfk_2, "
        "ALGORITHM=INPLACE, LOCK=NONE"
    )


def downgrade():
    op.execute(
        "ALTER TABLE member_track "
        "ADD CONSTRAINT member_track_ibfk_2 "
        "FOREIGN KEY (user_id) REFERENCES user(id)"
    )
