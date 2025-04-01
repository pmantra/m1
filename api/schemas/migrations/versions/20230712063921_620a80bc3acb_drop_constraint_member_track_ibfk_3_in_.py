"""drop-constraint-member-track-ibfk-3-in-member-track

Revision ID: 620a80bc3acb
Revises: 39ab40f16475
Create Date: 2023-07-12 06:39:21.245582+00:00

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "620a80bc3acb"
down_revision = "39ab40f16475"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "ALTER TABLE member_track "
        "DROP FOREIGN KEY member_track_ibfk_3, "
        "ALGORITHM=INPLACE, LOCK=NONE"
    )


def downgrade():
    op.execute(
        "ALTER TABLE member_track "
        "ADD CONSTRAINT member_track_ibfk_3 "
        "FOREIGN KEY (organization_employee_id) REFERENCES organization_employee(id)"
    )
