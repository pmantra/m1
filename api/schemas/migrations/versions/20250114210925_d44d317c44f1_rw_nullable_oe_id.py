"""rw_nullable_oe_id

Revision ID: d44d317c44f1
Revises: c791e2009c9c
Create Date: 2025-01-14 21:09:25.319210+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "d44d317c44f1"
down_revision = "c791e2009c9c"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """ALTER TABLE maven.reimbursement_wallet 
        MODIFY `organization_employee_id` int(11) NULL, 
        ALGORITHM=INPLACE, LOCK=NONE;"""
    )


def downgrade():
    # Since OE will be deprecated,
    # we will never go back to NOT NULL any more
    pass
