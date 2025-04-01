"""Configure Popular Library Topics per Track

Revision ID: 584e2adddf63
Revises: b96ab53e7131
Create Date: 2021-12-02 14:30:44.656919+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "584e2adddf63"
down_revision = "b96ab53e7131"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "popular_topics_per_track",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("track_name", sa.String(120), nullable=False),
        sa.Column("topic", sa.String(50), nullable=False),
        sa.Column("sort_order", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("modified_at", sa.DateTime, nullable=False),
    )

    op.create_unique_constraint(
        "popular_topic_track", "popular_topics_per_track", ["track_name", "topic"]
    )


def downgrade():
    op.drop_table("popular_topics_per_track")
