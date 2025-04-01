"""add and update tables for questionnaires

Revision ID: 6283041ec8b7
Revises: 27526ef71ab6
Create Date: 2020-04-23 17:57:23.354886

"""
from alembic import op
import sqlalchemy as sa
import enum
from storage.connection import db
from models.questionnaires import QuestionSet
import snowflake


# revision identifiers, used by Alembic.
revision = "6283041ec8b7"
down_revision = "1e76c90159ca"
branch_labels = None
depends_on = None


class OldQuestionTypes(enum.Enum):
    RADIO = "RADIO"
    CHECKBOX = "CHECKBOX"
    TEXT = "TEXT"


class QuestionTypes(enum.Enum):
    RADIO = "RADIO"
    CHECKBOX = "CHECKBOX"
    TEXT = "TEXT"
    STAR = "STAR"


def upgrade():
    conn = op.get_bind()
    inspector = sa.engine.reflection.Inspector.from_engine(conn)
    tables = inspector.get_table_names()

    if "questionnaire" not in tables:
        op.create_table(
            "questionnaire",
            sa.Column("id", sa.BigInteger, primary_key=True),
            sa.Column("sort_order", sa.Integer, nullable=False),
            # avoiding "Specified key was too long; max key length is 767 bytes" error
            sa.Column("name", sa.String(191), unique=True),
            sa.Column("title_text", sa.String(255)),
            sa.Column("description_text", sa.String(1000)),
        )
    # adding this, but not getting rid of old association table yet
    if "questionnaire_vertical" not in tables:
        op.create_table(
            "questionnaire_vertical",
            sa.Column(
                "questionnaire_id",
                sa.BigInteger,
                sa.ForeignKey("questionnaire.id"),
                nullable=False,
            ),
            sa.Column(
                "vertical_id", sa.Integer, sa.ForeignKey("vertical.id"), nullable=False
            ),
        )
    # more than one answer can trigger a questionnaire!
    if "questionnaire_trigger_answer" not in tables:
        op.create_table(
            "questionnaire_trigger_answer",
            sa.Column(
                "questionnaire_id",
                sa.BigInteger,
                sa.ForeignKey("questionnaire.id"),
                nullable=False,
            ),
            sa.Column(
                "answer_id", sa.BigInteger, sa.ForeignKey("answer.id"), nullable=False
            ),
        )
    if "questionnaire_role" not in tables:
        op.create_table(
            "questionnaire_role",
            sa.Column("role_id", sa.Integer, sa.ForeignKey("role.id"), nullable=False),
            sa.Column(
                "questionnaire_id",
                sa.BigInteger,
                sa.ForeignKey("questionnaire.id"),
                nullable=False,
            ),
        )

    qs_columns = inspector.get_columns("question_set")
    if "questionnaire_id" not in [col["name"] for col in qs_columns]:
        op.add_column(
            "question_set", sa.Column("questionnaire_id", sa.BigInteger, nullable=True)
        )

    op.alter_column(
        "question",
        "type",
        type_=sa.Enum(QuestionTypes),
        existing_type=sa.Enum(OldQuestionTypes),
        nullable=False,
    )

    # moving old question sets to a new questionnaire
    # in prod, at least, it's known that all existing should belong
    # to the post-appt note one, and they all share the same verticals

    if "question_set_vertical" in tables:
        question_sets = db.session.query(QuestionSet.id).all()
        question_set_verticals = [
            r for r in db.session.execute("SELECT * from question_set_vertical")
        ]

        if question_sets:
            questionnaire_id = snowflake.generate()
            db.session.execute(
                f"INSERT INTO questionnaire (id, sort_order, name) VALUES ({questionnaire_id}, 0, 'structured_internal_note')"
            )
            for qs in question_sets:
                db.session.execute(
                    f"UPDATE question_set SET questionnaire_id={questionnaire_id} WHERE id={qs.id}"
                )

                for qs_id, vert_id in question_set_verticals:
                    if qs_id == qs.id:
                        db.session.execute(
                            f"INSERT INTO questionnaire_vertical (questionnaire_id, vertical_id) VALUES ({questionnaire_id}, {vert_id})"
                        )
    # this has to be outside of the condition because if there are no question sets,
    # the transaction never closes and thus prevents the alter_column below :)))
    db.session.commit()

    # now that everyone has a questionnaire, we can make this a non-nullable foreign key
    op.alter_column(
        "question_set", "questionnaire_id", existing_type=sa.BigInteger, nullable=False
    )

    op.create_foreign_key(
        "fk_questionnaire_id",
        "question_set",
        "questionnaire",
        ["questionnaire_id"],
        ["id"],
    )


def downgrade():
    class QuestionTypes(enum.Enum):
        RADIO = "RADIO"
        CHECKBOX = "CHECKBOX"
        TEXT = "TEXT"

    class OldQuestionTypes(enum.Enum):
        RADIO = "RADIO"
        CHECKBOX = "CHECKBOX"
        TEXT = "TEXT"
        STAR = "STAR"

    conn = op.get_bind()
    inspector = sa.engine.reflection.Inspector.from_engine(conn)
    tables = inspector.get_table_names()

    op.alter_column(
        "question",
        "type",
        type_=sa.Enum(OldQuestionTypes),
        existing_type=sa.Enum(QuestionTypes),
        nullable=False,
    )

    qs_columns = inspector.get_columns("question_set")
    if "questionnaire_id" in [col["name"] for col in qs_columns]:
        op.drop_constraint("fk_questionnaire_id", "question_set", type_="foreignkey")
        op.drop_column("question_set", "questionnaire_id")
    if "questionnaire_role" in tables:
        op.drop_table("questionnaire_role")
    if "questionnaire_trigger_answer" in tables:
        op.drop_table("questionnaire_trigger_answer")
    if "questionnaire_vertical" in tables:
        op.drop_table("questionnaire_vertical")
    if "questionnaire" in tables:
        op.drop_table("questionnaire")
