"""member_health_plan_deprecated_column_nullable

Revision ID: 324a95a1a30f
Revises: 60b3cad6167b
Create Date: 2024-10-23 17:50:33.765049+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "324a95a1a30f"
down_revision = "60b3cad6167b"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `member_health_plan`
        MODIFY COLUMN `is_family_plan` tinyint(1),
        ALGORITHM=COPY, LOCK=SHARED;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `member_health_plan`
        MODIFY COLUMN `is_family_plan` tinyint(1) NOT NULL,
        ALGORITHM=COPY, LOCK=SHARED;
        """
    )
