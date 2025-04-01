"""Update question type enum and add fk to recorded answer set

Revision ID: 5e2f628e2994
Revises: 06e560ec6777
Create Date: 2020-09-16 17:16:36.782381

"""
from alembic import op
import sqlalchemy as sa
import enum


# revision identifiers, used by Alembic.
revision = "5e2f628e2994"
down_revision = "06e560ec6777"
branch_labels = None
depends_on = None


class OldQuestionTypes(enum.Enum):
    RADIO = "RADIO"
    CHECKBOX = "CHECKBOX"
    TEXT = "TEXT"
    STAR = "STAR"


class QuestionTypes(enum.Enum):
    RADIO = "RADIO"
    CHECKBOX = "CHECKBOX"
    TEXT = "TEXT"
    STAR = "STAR"
    MEDICATION = "MEDICATION"
    ALLERGY_INTOLERANCE = "ALLERGY_INTOLERANCE"
    CONDITION = "CONDITION"


def upgrade():
    op.alter_column(
        "question",
        "type",
        type_=sa.Enum(QuestionTypes),
        existing_type=sa.Enum(OldQuestionTypes),
        nullable=False,
    )

    op.add_column(
        "recorded_answer_set",
        sa.Column(
            "questionnaire_id",
            sa.BigInteger,
            sa.ForeignKey(
                "questionnaire.id", name="fk_rec_answer_set_questionnaire_id"
            ),
            nullable=True,
        ),
    )
    pass


def downgrade():
    op.alter_column(
        "question",
        "type",
        type_=sa.Enum(OldQuestionTypes),
        existing_type=sa.Enum(QuestionTypes),
        nullable=False,
    )

    op.drop_constraint(
        "fk_rec_answer_set_questionnaire_id", "recorded_answer_set", type_="foreignkey"
    )
    op.drop_column("recorded_answer_set", "questionnaire_id")
