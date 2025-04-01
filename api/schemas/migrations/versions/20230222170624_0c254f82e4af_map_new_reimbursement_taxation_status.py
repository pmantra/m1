"""map_new_reimbursement_taxation_status

Revision ID: 0c254f82e4af
Revises: 1fde6e015df6
Create Date: 2023-02-22 17:06:24.586742+00:00

"""
from __future__ import annotations

import pathlib

from alembic import op

from schemas.migrations.alembic_utils import get_migration_sql

PATH = pathlib.Path(__file__).resolve()
SQL_PATH = PATH.parent / f"{PATH.stem}.sql"

# revision identifiers, used by Alembic.
revision = "0c254f82e4af"
down_revision = "532874a11410"
branch_labels = None
depends_on = None


new_enum_mapping = {
    "QUALIFIED": "NON_TAXABLE",
    "NON_QUALIFIED": "TAXABLE",
}


def upgrade():
    up, down = get_migration_sql(SQL_PATH)
    op.execute(up)


def downgrade():
    up, down = get_migration_sql(SQL_PATH)
    op.execute(down)
