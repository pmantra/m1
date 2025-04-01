"""Add recorded answer set table

Revision ID: 0f04d48974ab
Revises: 843f53b7a0c9
Create Date: 2020-08-17 18:09:34.008598

"""
from alembic import op
import sqlalchemy as sa
from storage.connection import db

# revision identifiers, used by Alembic.
revision = "0f04d48974ab"
down_revision = "843f53b7a0c9"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.engine.reflection.Inspector.from_engine(conn)
    tables = inspector.get_table_names()

    if "recorded_answer_set" not in tables:
        op.create_table(
            "recorded_answer_set",
            sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=False),
            sa.Column("submitted_at", sa.DateTime),
            sa.Column(
                "source_user_id",
                sa.Integer,
                sa.ForeignKey("user.id", name="fk_source_user_id"),
                nullable=False,
            ),
        )

    ra_columns = inspector.get_columns("recorded_answer")
    if "recorded_answer_set_id" not in ra_columns:
        # drop foreign key constraint on appointment_id column so that it can be made nullable
        result = db.session.execute(
            "SELECT CONSTRAINT_NAME FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE WHERE REFERENCED_TABLE_SCHEMA = 'maven' AND TABLE_NAME = 'recorded_answer' AND COLUMN_NAME = 'appointment_id'"
        ).fetchone()
        if result:
            constraint_name = result[0]
            op.drop_constraint(constraint_name, "recorded_answer", type_="foreignkey")

        op.alter_column(
            "recorded_answer", "appointment_id", existing_type=sa.Integer, nullable=True
        )

        # recreate foreign key
        op.create_foreign_key(
            "fk_appointment_id",
            "recorded_answer",
            "appointment",
            ["appointment_id"],
            ["id"],
        )

        op.add_column(
            "recorded_answer",
            sa.Column(
                "recorded_answer_set_id",
                sa.BigInteger,
                sa.ForeignKey(
                    "recorded_answer_set.id", name="fk_recorded_answer_set_id"
                ),
            ),
        )


def downgrade():
    conn = op.get_bind()
    inspector = sa.engine.reflection.Inspector.from_engine(conn)
    tables = inspector.get_table_names()

    ra_columns = inspector.get_columns("recorded_answer")
    if "recorded_answer_set_id" in [col["name"] for col in ra_columns]:
        op.drop_constraint(
            "fk_recorded_answer_set_id", "recorded_answer", type_="foreignkey"
        )
        op.drop_column("recorded_answer", "recorded_answer_set_id")

        # drop appt foreign key constraint so column can be made un-nullable again, then re-add
        op.drop_constraint("fk_appointment_id", "recorded_answer", type_="foreignkey")
        op.alter_column(
            "recorded_answer",
            "appointment_id",
            existing_type=sa.BigInteger,
            nullable=False,
        )
        op.create_foreign_key(
            "fk_appointment_id",
            "recorded_answer",
            "appointment",
            ["appointment_id"],
            ["id"],
        )

    if "recorded_answer_set" in tables:
        op.drop_table("recorded_answer_set")
