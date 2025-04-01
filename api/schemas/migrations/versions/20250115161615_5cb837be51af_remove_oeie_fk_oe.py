"""remove_oeie_fk_oe

Revision ID: 5cb837be51af
Revises: d44d317c44f1
Create Date: 2025-01-15 16:16:15.252369+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "5cb837be51af"
down_revision = "d44d317c44f1"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "ALTER TABLE organization_employee_insurer_eligibility "
        "DROP FOREIGN KEY organization_employee_insurer_eligibility_ibfk_1, "
        "ALGORITHM=INPLACE, LOCK=NONE"
    )


def downgrade():
    op.execute(
        "DROP INDEX organization_employee_id ON organization_employee_insurer_eligibility"
    )
    op.execute(
        "CREATE INDEX organization_employee_id ON organization_employee_insurer_eligibility(organization_employee_id)"
    )
    op.execute(
        "ALTER TABLE organization_employee_insurer_eligibility "
        "ADD CONSTRAINT organization_employee_insurer_eligibility_ibfk_1 "
        "FOREIGN KEY (organization_employee_id) REFERENCES organization_employee(id)"
    )
