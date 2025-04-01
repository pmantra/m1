"""Add privilege_type to appointment

Revision ID: dab43c03a4b8
Revises: 53fae051ade4
Create Date: 2021-06-16 17:28:59.178668+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "dab43c03a4b8"
down_revision = "53fae051ade4"
branch_labels = None
depends_on = None


def upgrade():
    from models.common import PrivilegeType

    op.add_column(
        "appointment",
        sa.Column(
            "privilege_type",
            sa.Enum(
                PrivilegeType, values_callable=lambda _enum: [e.value for e in _enum]
            ),
        ),
    )


def downgrade():
    op.drop_column("appointment", "privilege_type")
