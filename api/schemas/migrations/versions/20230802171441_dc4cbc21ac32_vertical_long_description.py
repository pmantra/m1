"""vertical-long-description

Revision ID: dc4cbc21ac32
Revises: 3489990bc1b6
Create Date: 2023-08-02 17:14:41.828283+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "dc4cbc21ac32"
down_revision = "3489990bc1b6"
branch_labels = None
depends_on = None


def upgrade():
    # Not null with no default will initialize values to empty string
    op.execute(
        """
        ALTER TABLE vertical
        ADD COLUMN long_description VARCHAR(300) NOT NULL,
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE vertical
        DROP COLUMN long_description,
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )
