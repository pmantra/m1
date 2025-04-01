"""drop-constrains-in-member-track-table-1

Revision ID: b0b86604b18f
Revises: 2b829f95ca5c
Create Date: 2023-07-10 20:26:22.160768+00:00

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "b0b86604b18f"
down_revision = "2b829f95ca5c"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "ALTER TABLE member_track "
        "DROP FOREIGN KEY member_track_ibfk_1, "
        "ALGORITHM=INPLACE, LOCK=NONE"
    )


def downgrade():
    op.execute("DROP INDEX client_track_id ON member_track")
    op.execute("CREATE INDEX client_track_id ON member_track(client_track_id)")
    op.execute(
        "ALTER TABLE member_track "
        "ADD CONSTRAINT member_track_ibfk_1 "
        "FOREIGN KEY (client_track_id) REFERENCES client_track(id)"
    )
