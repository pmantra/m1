"""Create 'base' migration for initial schema

Revision ID: 2e35353ca713
Revises:
Create Date: 2021-08-25 19:04:58.415724+00:00

"""
import pathlib

from alembic import op
from sqlalchemy.sql import text

DIR = pathlib.Path(__file__).parent.resolve()
DEFAULT_SCHEMA = DIR.parent / "initial_default_schema.sql"


# revision identifiers, used by Alembic.
revision = "2e35353ca713"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    script = text(DEFAULT_SCHEMA.read_text())
    print(script)
    op.execute(script)


def downgrade():
    op.execute("DROP DATABASE IF EXISTS `maven`;")
    op.execute("CREATE DATABASE IF NOT EXISTS `maven`;")
