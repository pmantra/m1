"""add minor_unit to country_currency_code

Revision ID: 6318192ddd6f
Revises: 2ae48a561d61
Create Date: 2024-02-14 17:40:31.470642+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "6318192ddd6f"
down_revision = "d1e0256e1d90"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE maven.country_currency_code
        ADD COLUMN minor_unit TINYINT(2) DEFAULT NULL,
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )
    pass


def downgrade():
    op.execute(
        """
        ALTER TABLE maven.country_currency_code
        DROP COLUMN minor_unit,
        ALGORITHM=INPLACE, 
        LOCK=NONE;
        """
    )
    pass
