"""Update product constraint

Revision ID: b4bb1d32d5f0
Revises: d316ca01ed14
Create Date: 2020-03-31 22:09:18.206160

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "b4bb1d32d5f0"
down_revision = "d316ca01ed14"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("product_ibfk_1", "product", type_="foreignkey")
    op.drop_constraint("minutes", "product", type_="unique")
    op.create_unique_constraint(
        "uq_minutes_price", "product", ["user_id", "minutes", "price", "vertical_id"]
    )
    op.create_foreign_key("product_ibfk_1", "product", "user", ["user_id"], ["id"])


def downgrade():
    op.drop_constraint("product_ibfk_1", "product", type_="foreignkey")
    op.drop_constraint("uq_minutes_price", "product", type_="unique")
    op.create_unique_constraint(
        "minutes", "product", ["user_id", "minutes", "vertical_id"]
    )
    op.create_foreign_key("product_ibfk_1", "product", "user", ["user_id"], ["id"])
