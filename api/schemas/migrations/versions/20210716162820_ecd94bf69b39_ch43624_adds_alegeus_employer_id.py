"""ch43624 adds alegeus employer id

Revision ID: ecd94bf69b39
Revises: 0055cdc21010
Create Date: 2021-07-16 16:28:20.854084+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "ecd94bf69b39"
down_revision = "0055cdc21010"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "organization", sa.Column("alegeus_employer_id", sa.VARCHAR(12), nullable=True)
    )
    op.create_unique_constraint(
        "alegeus_employer_id", "organization", ["alegeus_employer_id"]
    )


def downgrade():
    op.drop_constraint("alegeus_employer_id", "organization", type_="unique")
    op.drop_column("organization", "alegeus_employer_id")
