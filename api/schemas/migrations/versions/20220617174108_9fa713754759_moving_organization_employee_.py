"""Moving organization_employee.eligibility_member_id to be unique

Revision ID: 9fa713754759
Revises: 212848e165b7
Create Date: 2022-06-17 17:41:08.108815+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "9fa713754759"
down_revision = "212848e165b7"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        "idx_ux_eligibility_member_id",
        "organization_employee",
        ["eligibility_member_id"],
        unique=True,
    )


def downgrade():
    op.drop_index("idx_ux_eligibility_member_id", "organization_employee")
