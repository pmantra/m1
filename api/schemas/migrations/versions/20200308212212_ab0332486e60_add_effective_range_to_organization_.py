"""Add effective range to organization_module_extension table.

Revision ID: ab0332486e60
Revises: 
Create Date: 2020-03-08 21:22:12.762606

"""
from datetime import date

from alembic import op
import sqlalchemy as sa

from models.enterprise import OrganizationModuleExtension as OME


# revision identifiers, used by Alembic.
revision = "ab0332486e60"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # TODO: share column definition with api/models
    op.add_column(
        "organization_module_extension",
        sa.Column("effective_from", sa.Date, nullable=True),
    )
    op.add_column(
        "organization_module_extension",
        sa.Column("effective_to", sa.Date, nullable=True),
    )
    op.execute(OME.__table__.update().values(effective_from=date(1970, 1, 1)))
    op.alter_column(
        "organization_module_extension",
        "effective_from",
        existing_type=sa.Date,
        nullable=False,
    )


def downgrade():
    for c in ("effective_from", "effective_to"):
        op.drop_column("organization_module_extension", c)
