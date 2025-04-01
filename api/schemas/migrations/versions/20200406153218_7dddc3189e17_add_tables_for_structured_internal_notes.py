"""add tables for structured internal notes

Revision ID: 7dddc3189e17
Revises: b4bb1d32d5f0
Create Date: 2020-04-06 15:32:18.623840

"""
from alembic import op
import sqlalchemy as sa
import enum


# revision identifiers, used by Alembic.
revision = "7dddc3189e17"
down_revision = "b4bb1d32d5f0"
branch_labels = None
depends_on = None


def upgrade():
    class QuestionTypes(enum.Enum):
        RADIO = "RADIO"
        CHECKBOX = "CHECKBOX"
        TEXT = "TEXT"

    op.create_table(
        "question_set",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=False),
        sa.Column("sort_order", sa.Integer, nullable=False),
    )

    op.create_table(
        "question_set_vertical",
        sa.Column(
            "vertical_id", sa.Integer, sa.ForeignKey("vertical.id"), nullable=False
        ),
        sa.Column(
            "question_set_id",
            sa.BigInteger,
            sa.ForeignKey("question_set.id"),
            nullable=False,
        ),
    )

    op.create_table(
        "question",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=False),
        sa.Column("sort_order", sa.Integer, nullable=False),
        sa.Column("label", sa.String(1000), nullable=False),
        sa.Column("type", sa.Enum(QuestionTypes), nullable=False),
        sa.Column("required", sa.Boolean, nullable=False),
        sa.Column("oid", sa.String(255), nullable=True),
        sa.Column(
            "question_set_id",
            sa.BigInteger,
            sa.ForeignKey("question_set.id"),
            nullable=False,
        ),
    )

    op.create_table(
        "answer",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=False),
        sa.Column("sort_order", sa.Integer, nullable=False),
        sa.Column("text", sa.String(1000), nullable=False),
        sa.Column("oid", sa.String(255), nullable=True),
        sa.Column(
            "question_id", sa.BigInteger, sa.ForeignKey("question.id"), nullable=False
        ),
    )

    op.create_table(
        "recorded_answer",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=False),
        sa.Column("text", sa.String(1000), nullable=True),
        sa.Column(
            "appointment_id",
            sa.Integer,
            sa.ForeignKey("appointment.id"),
            nullable=False,
        ),
        sa.Column(
            "question_id", sa.BigInteger, sa.ForeignKey("question.id"), nullable=False
        ),
        sa.Column(
            "answer_id", sa.BigInteger, sa.ForeignKey("answer.id"), nullable=True
        ),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("user.id"), nullable=False),
    )

    # have to do this at the end when answer table actually exists
    op.add_column(
        "question_set",
        sa.Column(
            "prerequisite_answer_id",
            sa.BigInteger,
            sa.ForeignKey(
                "answer.id", name="fk_prerequisite_answer_id", use_alter=True
            ),
            nullable=True,
        ),
    )


def downgrade():
    # to deal with circular dependency
    op.drop_constraint("fk_prerequisite_answer_id", "question_set", type_="foreignkey")
    op.drop_table("recorded_answer")
    op.drop_table("answer")
    op.drop_table("question")
    op.drop_table("question_set_vertical")
    op.drop_table("question_set")
