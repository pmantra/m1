"""Add new question types for date, multiselect, single select

Revision ID: ef25647f8390
Revises: daf8b259e08a
Create Date: 2021-05-12 22:22:53.496679+00:00

"""
from alembic import op
import sqlalchemy as sa
import enum


# revision identifiers, used by Alembic.
revision = "ef25647f8390"
down_revision = "daf8b259e08a"
branch_labels = None
depends_on = None


class OldQuestionTypes(enum.Enum):
    RADIO = "RADIO"
    CHECKBOX = "CHECKBOX"
    TEXT = "TEXT"
    STAR = "STAR"
    MEDICATION = "MEDICATION"
    ALLERGY_INTOLERANCE = "ALLERGY_INTOLERANCE"
    CONDITION = "CONDITION"


class QuestionTypes(enum.Enum):
    RADIO = "RADIO"
    CHECKBOX = "CHECKBOX"
    TEXT = "TEXT"
    STAR = "STAR"
    MEDICATION = "MEDICATION"
    ALLERGY_INTOLERANCE = "ALLERGY_INTOLERANCE"
    CONDITION = "CONDITION"
    DATE = "DATE"
    MULTISELECT = "MULTISELECT"
    SINGLE_SELECT = "SINGLE_SELECT"


def upgrade():
    op.alter_column(
        "question",
        "type",
        type_=sa.Enum(QuestionTypes),
        existing_type=sa.Enum(OldQuestionTypes),
        nullable=False,
    )

    op.add_column("recorded_answer", sa.Column("date", sa.Date, nullable=True))


def downgrade():
    op.alter_column(
        "question",
        "type",
        type_=sa.Enum(OldQuestionTypes),
        existing_type=sa.Enum(QuestionTypes),
        nullable=False,
    )

    op.drop_column("recorded_answer", "date")
