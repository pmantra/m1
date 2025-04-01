"""Create constraint to practitioner_track_vertical

Revision ID: f0c9620948af
Revises: 6ce33b3384c4
Create Date: 2022-05-23 16:21:07.440945+00:00

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "f0c9620948af"
down_revision = "6ce33b3384c4"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_column(table_name="practitioner_track_vertical", column_name="id")

    op.create_unique_constraint(
        constraint_name="uq_prac_track_vertical",
        table_name="practitioner_track_vertical",
        columns=["practitioner_id", "vertical_id", "track_name"],
    )


def downgrade():
    op.execute(
        "ALTER TABLE practitioner_track_vertical ADD id INT PRIMARY KEY AUTO_INCREMENT;"
    )

    op.drop_constraint(
        constraint_name="uq_prac_track_vertical",
        table_name="practitioner_track_vertical",
        type_="unique",
    )
