"""Add fkeys to legacy program tables on member track tables.

Revision ID: e2edd1cc2079
Revises: 186bf54851ee, 910e5b8adfb3
Create Date: 2020-10-12 18:41:48.681353

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "e2edd1cc2079"
down_revision = ("186bf54851ee", "910e5b8adfb3")
branch_labels = None
depends_on = None


def upgrade():
    op.create_foreign_key(
        None,
        "member_track_phase",
        "care_program_phase",
        ["legacy_program_phase_id"],
        ["id"],
    )
    op.create_foreign_key(
        None, "member_track", "care_program", ["legacy_program_id"], ["id"]
    )
    op.create_foreign_key(None, "member_track", "module", ["legacy_module_id"], ["id"])


def downgrade():
    op.drop_constraint(
        "member_track_phase_ibfk_2", "member_track_phase", type_="foreignkey"
    )
    op.drop_index("legacy_program_phase_id", "member_track_phase")
    op.drop_constraint("member_track_ibfk_4", "member_track", type_="foreignkey")
    op.drop_index("legacy_program_id", "member_track")
    op.drop_constraint("member_track_ibfk_5", "member_track", type_="foreignkey")
    op.drop_index("legacy_module_id", "member_track")
