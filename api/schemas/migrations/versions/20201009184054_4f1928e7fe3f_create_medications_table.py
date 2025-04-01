"""Create medications table

Revision ID: 4f1928e7fe3f
Revises: e2edd1cc2079
Create Date: 2020-10-09 18:40:54.958133

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "4f1928e7fe3f"
down_revision = "e2edd1cc2079"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "medications",
        sa.Column("product_id", sa.String(100)),
        sa.Column("product_ndc", sa.String(20)),
        sa.Column("product_type_name", sa.String(100)),
        sa.Column("proprietary_name", sa.String(1000), nullable=False),
        sa.Column("proprietary_name_suffix", sa.String(255)),
        sa.Column("nonproprietary_name", sa.String(1000), nullable=False),
        sa.Column("dosage_form_name", sa.String(100)),
        sa.Column("route_name", sa.String(255)),
        sa.Column("labeler_name", sa.String(255)),
        sa.Column("substance_name", sa.String(1000)),
        sa.Column("pharm_classes", sa.String(1000)),
        sa.Column("dea_schedule", sa.String(5)),
        sa.Column("listing_record_certified_through", sa.String(8)),
    )


def downgrade():
    op.drop_table("medications")
