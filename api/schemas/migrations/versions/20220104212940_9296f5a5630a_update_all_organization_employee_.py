"""Update all organization_employee records with an eligiblity_member_id of 0 to None

Revision ID: 9296f5a5630a
Revises: d4d9af2d349d
Create Date: 2022-01-04 21:29:40.870445+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "9296f5a5630a"
down_revision = "d4d9af2d349d"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "UPDATE organization_employee SET eligibility_member_id = NULL WHERE eligibility_member_id = 0"
    )


def downgrade():
    pass
