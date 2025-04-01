"""health_profile_json_expand

Revision ID: 13de312f2e79
Revises: 7cdb82dc8091
Create Date: 2022-10-17 16:36:33.022996+00:00

"""
from alembic import op
import sqlalchemy as sa

from health.models.health_profile import HealthProfile

# revision identifiers, used by Alembic.
revision = "13de312f2e79"
down_revision = "7cdb82dc8091"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(HealthProfile.__tablename__, sa.Column("bmi", sa.Float))
    op.add_column(HealthProfile.__tablename__, sa.Column("age", sa.Integer))
    op.add_column(HealthProfile.__tablename__, sa.Column("children_string", sa.Text))
    op.add_column(
        HealthProfile.__tablename__,
        sa.Column("children_with_age_string", sa.Text),
    )
    op.add_column(
        HealthProfile.__tablename__, sa.Column("last_child_birthday", sa.DateTime)
    )


def downgrade():
    op.drop_column(HealthProfile.__tablename__, "bmi")
    op.drop_column(HealthProfile.__tablename__, "age")
    op.drop_column(HealthProfile.__tablename__, "children_string")
    op.drop_column(HealthProfile.__tablename__, "children_with_age_string")
    op.drop_column(HealthProfile.__tablename__, "last_child_birthday")
