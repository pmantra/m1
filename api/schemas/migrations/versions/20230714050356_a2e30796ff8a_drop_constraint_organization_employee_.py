"""drop-constraint-organization-employee-ibfk-1

Revision ID: a2e30796ff8a
Revises: 3f882c51ab8c
Create Date: 2023-07-14 05:03:56.968064+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "a2e30796ff8a"
down_revision = "9b1da7691012"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "ALTER TABLE organization_employee "
        "DROP FOREIGN KEY organization_employee_ibfk_1, "
        "ALGORITHM=INPLACE, LOCK=NONE"
    )


def downgrade():
    op.execute(
        "ALTER TABLE organization_employee "
        "ADD CONSTRAINT organization_employee_ibfk_1 "
        "FOREIGN KEY (organization_id) REFERENCES organization(id)"
    )
