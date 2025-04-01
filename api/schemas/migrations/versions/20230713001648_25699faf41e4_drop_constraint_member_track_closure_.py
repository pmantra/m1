"""drop-constraint-member-track-closure-reason-id-fk-in-member-track

Revision ID: 25699faf41e4
Revises: e28b272f602e
Create Date: 2023-07-13 00:16:48.779968+00:00

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "25699faf41e4"
down_revision = "e28b272f602e"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "ALTER TABLE member_track "
        "DROP FOREIGN KEY member_track_closure_reason_id_fk, "
        "ALGORITHM=INPLACE, LOCK=NONE"
    )


def downgrade():
    op.execute(
        "ALTER TABLE member_track "
        "ADD CONSTRAINT member_track_closure_reason_id_fk "
        "FOREIGN KEY (closure_reason_id) REFERENCES track_change_reason(id)"
    )
