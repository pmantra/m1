"""remove category label unique constraint

Revision ID: ed68860d80b3
Revises: 3e1ddc82ccfe
Create Date: 2021-10-07 14:17:23.117119+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "ed68860d80b3"
down_revision = "3e1ddc82ccfe"
branch_labels = None
depends_on = None


# TODO: dump default_schema
def upgrade():
    op.drop_constraint("label", "reimbursement_request_category", type_="unique")


def downgrade():
    op.create_unique_constraint("label", "reimbursement_request_category", ["label"])
