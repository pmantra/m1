"""make_aa_max_capacity_and_daily_intro_capacity_not_none

Revision ID: df4d1f49b51a
Revises: 7ddeec3fd048
Create Date: 2023-03-09 15:51:50.662372+00:00

"""
from alembic import op
import sqlalchemy as sa
from care_advocates.models.assignable_advocates import AssignableAdvocate

# revision identifiers, used by Alembic.
revision = "df4d1f49b51a"
down_revision = "87024c6955bf"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        AssignableAdvocate.__tablename__,
        "max_capacity",
        existing_type=sa.SmallInteger,
        nullable=False,
        default=0,
    )
    op.alter_column(
        AssignableAdvocate.__tablename__,
        "daily_intro_capacity",
        existing_type=sa.SmallInteger,
        nullable=False,
        default=0,
    )


def downgrade():
    op.alter_column(
        AssignableAdvocate.__tablename__,
        "max_capacity",
        existing_type=sa.SmallInteger,
        nullable=True,
    )
    op.alter_column(
        AssignableAdvocate.__tablename__,
        "daily_intro_capacity",
        existing_type=sa.SmallInteger,
        nullable=True,
    )
