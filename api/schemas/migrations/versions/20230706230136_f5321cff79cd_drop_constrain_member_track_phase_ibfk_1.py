"""drop-constrains-member_track_phase_ibfk_1-in-member_track_phase table

Revision ID: f5321cff79cd
Revises: a18b855f4c40
Create Date: 2023-07-06 23:01:36.683159+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "f5321cff79cd"
down_revision = "19bc69120f88"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "ALTER TABLE member_track_phase "
        "DROP FOREIGN KEY member_track_phase_ibfk_1, "
        "ALGORITHM=INPLACE, LOCK=NONE"
    )


def downgrade():
    op.execute("DROP INDEX member_track_id ON member_track_phase")
    op.execute("CREATE INDEX member_track_id ON member_track_phase(member_track_id);")
    op.execute(
        "ALTER TABLE member_track_phase "
        "ADD CONSTRAINT member_track_phase_ibfk_1 "
        "FOREIGN KEY (member_track_id) REFERENCES member_track(id)"
    )
