"""Add virtual_event_user_registration table

Revision ID: ac005a927c1a
Revises: 4318fa20a399
Create Date: 2022-07-12 16:50:27.633879+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "ac005a927c1a"
down_revision = "4318fa20a399"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "virtual_event_user_registration",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer,
            sa.ForeignKey("user.id"),
            nullable=False,
        ),
        sa.Column(
            "virtual_event_id",
            sa.Integer,
            sa.ForeignKey("virtual_event.id"),
            nullable=False,
        ),
    )
    op.create_unique_constraint(
        "virtual_event_id_user_id_unique",
        "virtual_event_user_registration",
        ["virtual_event_id", "user_id"],
    )


def downgrade():
    op.drop_table("virtual_event_user_registration")
