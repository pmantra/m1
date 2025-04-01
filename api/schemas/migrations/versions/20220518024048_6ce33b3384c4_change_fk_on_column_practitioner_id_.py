"""Change FK on column practitioner_id table practitioner_track_vertical
Associate it with practitoner_profile rather than with user

Revision ID: 6ce33b3384c4
Revises: 08fe07727ef7
Create Date: 2022-05-18 02:40:48.233216+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "6ce33b3384c4"
down_revision = "08fe07727ef7"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint(
        "practitioner_track_vertical_ibfk_1",
        "practitioner_track_vertical",
        type_="foreignkey",
    )

    op.create_foreign_key(
        constraint_name="practitioner_track_vertical_ibfk_1",
        source_table="practitioner_track_vertical",
        referent_table="practitioner_profile",
        local_cols=["practitioner_id"],
        remote_cols=["user_id"],
    )


def downgrade():
    op.drop_constraint(
        "practitioner_track_vertical_ibfk_1",
        "practitioner_track_vertical",
        type_="foreignkey",
    )
    op.create_foreign_key(
        constraint_name="practitioner_track_vertical_ibfk_1",
        source_table="practitioner_track_vertical",
        referent_table="user",
        local_cols=["practitioner_id"],
        remote_cols=["id"],
    )
