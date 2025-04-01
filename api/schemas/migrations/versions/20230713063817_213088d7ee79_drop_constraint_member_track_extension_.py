"""drop-constraint-member-track-extension-id-fk-in-member-track

Revision ID: 213088d7ee79
Revises: 25699faf41e4
Create Date: 2023-07-13 06:38:17.014604+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "213088d7ee79"
down_revision = "25699faf41e4"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "ALTER TABLE member_track "
        "DROP FOREIGN KEY member_track_extension_id_fk, "
        "ALGORITHM=INPLACE, LOCK=NONE"
    )


def downgrade():
    op.execute(
        "ALTER TABLE member_track "
        "ADD CONSTRAINT member_track_extension_id_fk "
        "FOREIGN KEY (track_extension_id) REFERENCES track_extension(id)"
    )
