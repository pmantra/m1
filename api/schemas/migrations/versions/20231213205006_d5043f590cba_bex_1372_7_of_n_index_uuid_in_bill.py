"""BEX-1372_7_of_n_index_uuid_in bill

Revision ID: d5043f590cba
Revises: 09c68ac9fde8
Create Date: 2023-12-13 20:50:06.135262+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "d5043f590cba"
down_revision = "09c68ac9fde8"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(index_name="ix_bill_uuid", table_name="bill", columns=["uuid"])


def downgrade():
    op.drop_index(index_name="ix_bill_uuid", table_name="bill")
