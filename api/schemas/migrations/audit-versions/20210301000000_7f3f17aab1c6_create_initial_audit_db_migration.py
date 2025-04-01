"""Create initial audit db migration

Revision ID: 7f3f17aab1c6
Revises: 
Create Date: 2021-03-01 00:00:00.000000+00:00

"""
import pathlib

from alembic import op
from sqlalchemy.sql import text

DIR = pathlib.Path(__file__).parent.resolve()
DEFAULT_SCHEMA = DIR.parent / "initial_audit_schema.sql"


# revision identifiers, used by Alembic.
revision = "7f3f17aab1c6"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    script = text(DEFAULT_SCHEMA.read_text())
    print(script)
    op.execute(script)


def downgrade():
    op.execute("DROP DATABASE IF EXISTS `audit`;")
    op.execute("CREATE DATABASE IF NOT EXISTS `audit`;")
