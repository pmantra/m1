"""Add assessment_lifecycle_tracks

Revision ID: 04aefe527bf1
Revises: 7dc1f518a2df, 2eb39ac20baa
Create Date: 2020-10-06 20:30:39.940536

"""
import sqlalchemy as sa
from alembic import op

from models.enterprise import AssessmentLifecycle, AssessmentLifecycleTrack
from models.programs import Module, Phase
from storage.connection import db

# revision identifiers, used by Alembic.
revision = "04aefe527bf1"
down_revision = ("7dc1f518a2df", "2eb39ac20baa")
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "assessment_lifecycle_tracks",
        sa.Column(
            "assessment_lifecycle_id",
            sa.Integer,
            sa.ForeignKey("assessment_lifecycle.id"),
            primary_key=True,
        ),
        sa.Column("track_name", sa.String(120), primary_key=True),
        sa.UniqueConstraint("track_name"),
    )
    backfill_assessment_lifecycle_tracks()


def downgrade():
    op.drop_table("assessment_lifecycle_tracks")


def backfill_assessment_lifecycle_tracks():
    rows = _get_assessment_lifecycle_tracks()
    db.session.bulk_insert_mappings(
        AssessmentLifecycleTrack, [row._asdict() for row in rows]
    )
    db.session.commit()


def _get_assessment_lifecycle_tracks():
    return (
        db.s_replica1.query(
            AssessmentLifecycle.id.label("assessment_lifecycle_id"),
            Module.name.label("track_name"),
        )
        .join(
            Phase,
            Phase.onboarding_assessment_lifecycle_id == AssessmentLifecycle.id,
            isouter=True,
        )
        .join(Module, Module.id == Phase.module_id, isouter=True)
        .group_by(Module.name, AssessmentLifecycle.id)
        .filter(Module.name.isnot(None))
        .all()
    )
