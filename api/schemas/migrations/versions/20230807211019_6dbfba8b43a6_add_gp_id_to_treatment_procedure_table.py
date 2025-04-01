"""add_gp_id_to_treatment_procedure_table

Revision ID: 6dbfba8b43a6
Revises: 929f151dda70
Create Date: 2023-08-07 21:10:19.396482+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "6dbfba8b43a6"
down_revision = "929f151dda70"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "treatment_procedure",
        sa.Column(
            "global_procedure_id",
            sa.String(36),
            nullable=True,
        ),
    )


def downgrade():
    op.drop_column("treatment_procedure", "global_procedure_id")
