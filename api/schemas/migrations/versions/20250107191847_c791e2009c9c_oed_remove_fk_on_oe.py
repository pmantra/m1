"""oed_remove_fk_on_oe

Revision ID: c791e2009c9c
Revises: ffcd844379f0
Create Date: 2025-01-07 19:18:47.587074+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "c791e2009c9c"
down_revision = "ffcd844379f0"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "ALTER TABLE organization_employee_dependent "
        "DROP FOREIGN KEY organization_employee_dependent_ibfk_1, "
        "ALGORITHM=INPLACE, LOCK=NONE"
    )


def downgrade():
    op.execute("DROP INDEX organization_employee_id ON organization_employee_dependent")
    op.execute(
        "CREATE INDEX organization_employee_id ON organization_employee_dependent(organization_employee_id)"
    )
    op.execute(
        "ALTER TABLE organization_employee_dependent "
        "ADD CONSTRAINT organization_employee_dependent_ibfk_1 "
        "FOREIGN KEY (organization_employee_id) REFERENCES organization_employee(id)"
    )
