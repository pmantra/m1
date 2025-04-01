"""add_key_e9y_member_id_mt

Revision ID: b3c335dce625
Revises: 5633c8e96d92
Create Date: 2024-09-04 00:52:11.167327+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "b3c335dce625"
down_revision = "5633c8e96d92"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE member_track 
        ADD KEY `idx_eligibility_member_id` (`eligibility_member_id`),
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE member_track 
        DROP KEY `idx_eligibility_member_id`,
        ALGORITHM=INPLACE,
        LOCK=NONE;
            """
    )
