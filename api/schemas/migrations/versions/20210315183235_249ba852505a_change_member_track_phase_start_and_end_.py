"""Change member_track_phase start and end column type to date

Revision ID: 249ba852505a
Revises: 285553f32120
Create Date: 2021-03-15 18:32:35.576285

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "249ba852505a"
down_revision = "285553f32120"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "member_track_phase", "started_at", type_=sa.Date, existing_nullable=False
    )

    # This column can be nullable if it is the user's current phase.
    op.alter_column(
        "member_track_phase", "ended_at", type_=sa.Date, existing_nullable=True
    )


def downgrade():
    op.alter_column(
        "member_track_phase", "started_at", type_=sa.DateTime, existing_nullable=False
    )

    # This column can be nullable if it is the user's current phase.
    op.alter_column(
        "member_track_phase", "ended_at", type_=sa.DateTime, existing_nullable=True
    )
