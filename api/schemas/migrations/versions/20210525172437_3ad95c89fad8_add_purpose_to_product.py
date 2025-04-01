"""Add purpose to product

Revision ID: 3ad95c89fad8
Revises: ef25647f8390
Create Date: 2021-05-25 17:24:37.323073+00:00

"""
import enum
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "3ad95c89fad8"
down_revision = "ef25647f8390"
branch_labels = None
depends_on = None


def upgrade():
    class Purposes(enum.Enum):
        BIRTH_PLANNING = "birth_planning"
        # Don't anticipate needing these others anytime soon, but...
        # consistency with appointment purpose? ¯\_(ツ)_/¯
        BIRTH_NEEDS_ASSESSMENT = "birth_needs_assessment"
        POSTPARTUM_NEEDS_ASSESSMENT = "postpartum_needs_assessment"
        INTRODUCTION = "introduction"
        INTRODUCTION_EGG_FREEZING = "introduction_egg_freezing"
        INTRODUCTION_FERTILITY = "introduction_fertility"

    op.add_column("product", sa.Column("purpose", sa.Enum(Purposes), nullable=True))


def downgrade():
    op.drop_column("product", "purpose")
