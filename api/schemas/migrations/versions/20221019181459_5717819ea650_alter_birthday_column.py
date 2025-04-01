"""alter_birthday_column

Revision ID: 5717819ea650
Revises: 5b920d2d16b0
Create Date: 2022-10-19 18:14:59.820050+00:00

"""
from alembic import op
import sqlalchemy as sa

from health.models.health_profile import HealthProfile

# revision identifiers, used by Alembic.
revision = "5717819ea650"
down_revision = "5b920d2d16b0"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        HealthProfile.__tablename__,
        column_name="children_string",
        new_column_name="children_persisted",
        existing_type=sa.Text,
    )
    op.alter_column(
        HealthProfile.__tablename__,
        column_name="children_with_age_string",
        new_column_name="children_with_age_persisted",
        existing_type=sa.Text,
    )
    op.alter_column(
        HealthProfile.__tablename__,
        column_name="last_child_birthday",
        new_column_name="last_child_birthday_persisted",
        existing_type=sa.DateTime,
        type_=sa.Date,
    )
    op.alter_column(
        HealthProfile.__tablename__,
        column_name="bmi",
        new_column_name="bmi_persisted",
        existing_type=sa.Float,
    )
    op.alter_column(
        HealthProfile.__tablename__,
        column_name="age",
        new_column_name="age_persisted",
        existing_type=sa.Integer,
    )


def downgrade():
    op.alter_column(
        HealthProfile.__tablename__,
        column_name="last_child_birthday_persisted",
        new_column_name="last_child_birthday",
        existing_type=sa.Date,
        type_=sa.DateTime,
    )

    op.alter_column(
        HealthProfile.__tablename__,
        new_column_name="children_string",
        column_name="children_persisted",
        existing_type=sa.Text,
    )
    op.alter_column(
        HealthProfile.__tablename__,
        new_column_name="children_with_age_string",
        column_name="children_with_age_persisted",
        existing_type=sa.Text,
    )
    op.alter_column(
        HealthProfile.__tablename__,
        new_column_name="bmi",
        column_name="bmi_persisted",
        existing_type=sa.Float,
    )
    op.alter_column(
        HealthProfile.__tablename__,
        new_column_name="age",
        column_name="age_persisted",
        existing_type=sa.Integer,
    )
