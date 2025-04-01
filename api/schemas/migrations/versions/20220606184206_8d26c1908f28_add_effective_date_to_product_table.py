"""Add effective date to product table

Revision ID: 8d26c1908f28
Revises: 878daae2c0b7
Create Date: 2022-06-06 18:42:06.979232+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "8d26c1908f28"
down_revision = "878daae2c0b7"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "product",
        sa.Column(
            "effective_date",
            sa.Date,
            nullable=False,
            default=sa.func.current_date(),
        ),
    )

    # Set existing record dates
    op.execute("UPDATE product SET effective_date = CURRENT_DATE")

    # Delete the foreign key and unique key first
    op.drop_constraint("product_ibfk_1", "product", type_="foreignkey")
    op.drop_constraint("uq_minutes_price", "product", type_="unique")

    # Create the new unique key and re-add the foreign key
    op.create_unique_constraint(
        "uq_minutes_price_date",
        "product",
        ["user_id", "minutes", "price", "vertical_id", "effective_date"],
    )
    op.create_foreign_key("product_ibfk_1", "product", "user", ["user_id"], ["id"])


def downgrade():
    op.drop_constraint("product_ibfk_1", "product", type_="foreignkey")
    op.drop_constraint("uq_minutes_price_date", "product", type_="unique")
    op.create_unique_constraint(
        "uq_minutes_price", "product", ["user_id", "minutes", "price", "vertical_id"]
    )
    op.drop_column("product", "effective_date")
    op.create_foreign_key("product_ibfk_1", "product", "user", ["user_id"], ["id"])
