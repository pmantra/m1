"""drop-constraint-member-track-previous-id-fk-in-member-track

Revision ID: 3f882c51ab8c
Revises: 1687d347af25
Create Date: 2023-07-13 22:30:48.699991+00:00

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "3f882c51ab8c"
down_revision = "1687d347af25"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "ALTER TABLE member_track "
        "DROP FOREIGN KEY member_track_previous_id_fk, "
        "ALGORITHM=INPLACE, LOCK=NONE"
    )


def downgrade():
    op.execute(
        "ALTER TABLE member_track "
        "ADD CONSTRAINT member_track_previous_id_fk "
        "FOREIGN KEY (previous_member_track_id) REFERENCES member_track(id)"
    )
