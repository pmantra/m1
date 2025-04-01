"""Add legacy relational columns for MemberTrack/MemberTrackPhase

Revision ID: 3b93df61d52b
Revises: 3eae69ae3a60
Create Date: 2020-09-08 19:09:05.265971

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "3b93df61d52b"
down_revision = "3eae69ae3a60"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("member_track") as batch_op:
        batch_op.add_column(sa.Column("legacy_program_id", sa.Integer, nullable=True))
        batch_op.add_column(sa.Column("legacy_module_id", sa.Integer, nullable=True))
    op.add_column(
        "member_track_phase",
        sa.Column("legacy_program_phase_id", sa.Integer, nullable=True),
    )


def downgrade():
    with op.batch_alter_table("member_track") as batch_op:
        batch_op.drop_column("legacy_program_id")
        batch_op.drop_column("legacy_module_id")
    op.drop_column("member_track_phase", "legacy_program_phase_id")
