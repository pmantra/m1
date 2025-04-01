"""remove_unique_name_constraint

Revision ID: b663614483be
Revises: ad0f786758da
Create Date: 2023-06-21 19:22:18.993123+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "b663614483be"
down_revision = "ad0f786758da"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "DROP INDEX need_categories_uq_1 ON need_category ALGORITHM=inplace LOCK=none; "
    )
    op.execute("DROP INDEX needs_uq_1 ON need ALGORITHM=inplace LOCK=none;")


def downgrade():
    op.execute(
        "ALTER TABLE need_category ADD CONSTRAINT need_categories_uq_1 UNIQUE (name), ALGORITHM=inplace, LOCK=none;"
    )
    op.execute(
        "ALTER TABLE need ADD CONSTRAINT needs_uq_1 UNIQUE (name), ALGORITHM=inplace, LOCK=none;"
    )
