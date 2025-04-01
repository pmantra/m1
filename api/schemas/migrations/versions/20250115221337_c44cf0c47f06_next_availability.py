"""next_availability

Revision ID: c44cf0c47f06
Revises: 85994049c25d
Create Date: 2025-01-15 22:13:37.767609+00:00

"""
import pathlib
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c44cf0c47f06"
down_revision = "85994049c25d"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "practitioner_data",
        sa.Column("next_availability", sa.DateTime(), nullable=True),
    )

    current_file = pathlib.Path(__file__).resolve()
    sql_file = current_file.parent / f"{current_file.stem}.sql"
    migration = sql_file.read_text()
    parts = migration.split("$$")[1:]
    connection = op.get_bind()
    with connection.begin():
        for sql in parts:
            connection.execute(sql)


def downgrade():
    op.execute(
        """
        DROP TRIGGER IF EXISTS `after_next_availability_update`;
        DROP TRIGGER IF EXISTS `after_next_availability_delete`;
        """
    )

    op.drop_column("practitioner_data", "next_availability")
