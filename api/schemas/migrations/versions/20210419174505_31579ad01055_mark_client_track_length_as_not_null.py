"""Mark client track length as not null

Revision ID: 31579ad01055
Revises: a7dba4ca6947
Create Date: 2021-04-19 17:45:05.509148+00:00

"""
from alembic import op
import sqlalchemy as sa
from storage.connection import db


# revision identifiers, used by Alembic.
revision = "31579ad01055"
down_revision = "a7dba4ca6947"
branch_labels = None
depends_on = None


def upgrade():
    db.session.remove()
    null_count = db.session.execute(
        "SELECT COUNT(*) FROM client_track WHERE length_in_days IS NULL"
    ).scalar()
    if null_count > 0:
        raise Exception(
            """
Not all client tracks have a length_in_days set. Please run the following code in a dev shell:
  
from utils.migrations.populate_client_track_length import run
run(dry_run=False)
  
OR, run as one command:
  
api-exec bash -c "echo 'from utils.migrations.populate_client_track_length import run; run(dry_run=False)' | dev shell"

THEN, re-run alembic upgrade heads.
"""
        )
    db.session.remove()
    op.alter_column(
        "client_track", "length_in_days", existing_type=sa.Integer, nullable=False
    )


def downgrade():
    op.alter_column(
        "client_track", "length_in_days", existing_type=sa.Integer, nullable=True
    )
