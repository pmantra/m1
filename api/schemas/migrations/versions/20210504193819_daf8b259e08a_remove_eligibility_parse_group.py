"""Remove eligibility_parse_group

Revision ID: daf8b259e08a
Revises: fa5a192e7a1b
Create Date: 2021-05-04 19:38:19.128551+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "daf8b259e08a"
down_revision = "fa5a192e7a1b"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_table("eligibility_parse_group")


def downgrade():
    op.create_table(
        "eligibility_parse_group",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("created_at", sa.DateTime),
        sa.Column("modified_at", sa.DateTime),
    )
