"""Add status field for BMS orders

Revision ID: 69fd5b3294f0
Revises: 9fa713754759
Create Date: 2022-06-23 19:21:44.687905+00:00

"""
from alembic import op
import sqlalchemy as sa
from bms.models.bms import BMSOrder, OrderStatus


# revision identifiers, used by Alembic.
revision = "69fd5b3294f0"
down_revision = "9fa713754759"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        BMSOrder.__tablename__,
        sa.Column(
            "status",
            sa.Enum(OrderStatus),
            nullable=False,
        ),
    )
    op.create_index("status", BMSOrder.__tablename__, ["status"])
    op.create_index(
        "travel_start_date_status",
        BMSOrder.__tablename__,
        ["travel_start_date", "status"],
    )


def downgrade():
    op.drop_column(BMSOrder.__tablename__, "status")
    op.drop_index("travel_start_date_status", BMSOrder.__tablename__)
