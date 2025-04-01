"""chenwang/COCO-453/registration_form_url_nullable_migration

Revision ID: 690f6242b8df
Revises: e501d62a6d76
Create Date: 2023-09-28 16:54:26.382671+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "690f6242b8df"
down_revision = "e501d62a6d76"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "virtual_event",
        "registration_form_url",
        existing_type=sa.String(255),
        nullable=True,
    )


def downgrade():
    op.alter_column(
        "virtual_event",
        "registration_form_url",
        existing_type=sa.String(255),
        nullable=False,
    )
