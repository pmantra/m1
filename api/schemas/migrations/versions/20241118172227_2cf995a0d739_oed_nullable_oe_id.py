"""oed_nullable_oe_id

Revision ID: 2cf995a0d739
Revises: 4c4556d86998
Create Date: 2024-11-18 17:22:27.681177+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "2cf995a0d739"
down_revision = "4bcaea3f8578"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """ALTER TABLE maven.organization_employee_dependent 
        MODIFY `organization_employee_id` int(11) NULL, 
        ALGORITHM=INPLACE, LOCK=NONE;"""
    )


def downgrade():
    # Since OE will be deprecated,
    # we will never go back to NOT NULL any more
    pass
