"""member_track_nullable_start_date

Revision ID: 0f2481e2ce97
Revises: 23e4b7f60ba8
Create Date: 2023-10-25 13:28:57.474892+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "0f2481e2ce97"
down_revision = "23e4b7f60ba8"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "ALTER TABLE `member_track` MODIFY `start_date` date NOT NULL, LOCK=SHARED;"
    )


def downgrade():
    op.execute("ALTER TABLE `member_track` MODIFY `start_date` date;")
