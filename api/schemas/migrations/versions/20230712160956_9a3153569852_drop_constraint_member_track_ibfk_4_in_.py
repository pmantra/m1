"""drop-constraint-member-track-ibfk-4-in-member-track

Revision ID: 9a3153569852
Revises: 620a80bc3acb
Create Date: 2023-07-12 16:09:56.317445+00:00

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "9a3153569852"
down_revision = "620a80bc3acb"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "ALTER TABLE member_track "
        "DROP FOREIGN KEY member_track_ibfk_4, "
        "ALGORITHM=INPLACE, LOCK=NONE"
    )


def downgrade():
    op.execute(
        "ALTER TABLE member_track "
        "ADD CONSTRAINT member_track_ibfk_4 "
        "FOREIGN KEY (legacy_program_id) REFERENCES care_program(id)"
    )
