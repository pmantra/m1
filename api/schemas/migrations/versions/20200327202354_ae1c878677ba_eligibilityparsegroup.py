"""EligibilityParseBatch

Revision ID: ae1c878677ba
Revises: d316ca01ed14
Create Date: 2020-03-27 20:23:54.446878

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "ae1c878677ba"
down_revision = "d316ca01ed14"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "eligibility_parse_group",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("created_at", sa.DateTime),
        sa.Column("modified_at", sa.DateTime),
    )
    op.add_column(
        "eligibility_parse_record",
        sa.Column(
            "eligibility_parse_group_id",
            sa.Integer,
            sa.ForeignKey("eligibility_parse_group.id"),
        ),
    )


def downgrade():
    op.drop_constraint(
        "eligibility_parse_record_ibfk_2",
        "eligibility_parse_record",
        type_="foreignkey",
    )
    op.drop_column("eligibility_parse_record", "eligibility_parse_group_id")
    op.drop_table("eligibility_parse_group")
