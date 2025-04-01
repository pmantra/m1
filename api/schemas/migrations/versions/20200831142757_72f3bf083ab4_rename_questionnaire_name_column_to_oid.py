"""rename_questionnaire_name_column_to_oid

Revision ID: 72f3bf083ab4
Revises: 0f04d48974ab
Create Date: 2020-08-31 14:27:57.759203

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "72f3bf083ab4"
down_revision = "0f04d48974ab"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "questionnaire", "name", new_column_name="oid", existing_type=sa.String(191)
    )
    # also create empty name column to avoid breakage
    op.add_column("questionnaire", sa.Column("name", sa.String(191)))


def downgrade():
    op.drop_column("questionnaire", "name")
    op.alter_column(
        "questionnaire", "oid", new_column_name="name", existing_type=sa.String(191)
    )
