"""drop-constrain_member_track_phase_ibfk_2

Revision ID: 2b829f95ca5c
Revises: f5321cff79cd
Create Date: 2023-07-10 16:04:32.334310+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "2b829f95ca5c"
down_revision = "55ee133d365d"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "ALTER TABLE member_track_phase "
        "DROP FOREIGN KEY member_track_phase_ibfk_2, "
        "ALGORITHM=INPLACE, LOCK=NONE"
    )


def downgrade():
    op.execute("DROP INDEX legacy_program_phase_id ON member_track_phase")
    op.execute(
        "CREATE INDEX legacy_program_phase_id ON member_track_phase(legacy_program_phase_id);"
    )
    op.execute(
        "ALTER TABLE member_track_phase "
        "ADD CONSTRAINT member_track_phase_ibfk_2 "
        "FOREIGN KEY (legacy_program_phase_id) REFERENCES care_program_phase(id)"
    )
