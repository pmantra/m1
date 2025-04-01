"""Add in_house_fullfilment column, update track_id to track_ids column

Revision ID: 186bf54851ee
Revises: 04aefe527bf1
Create Date: 2020-10-09 15:14:50.827777

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "186bf54851ee"
down_revision = "04aefe527bf1"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "bms_order",
        sa.Column("is_maven_in_house_fulfillment", sa.Boolean, default=False),
    )
    op.alter_column(
        "bms_shipment",
        "tracking_number",
        new_column_name="tracking_numbers",
        existing_type=sa.String(255),
        existing_nullable=True,
    )


def downgrade():
    op.alter_column(
        "bms_shipment",
        "tracking_numbers",
        new_column_name="tracking_number",
        existing_type=sa.String(255),
        existing_nullable=True,
    )

    op.drop_column("bms_order", "is_maven_in_house_fulfillment")
