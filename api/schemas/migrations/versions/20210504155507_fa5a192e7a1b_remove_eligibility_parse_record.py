"""Remove eligibility_parse_record

Revision ID: fa5a192e7a1b
Revises: 654e34b39c96
Create Date: 2021-05-04 15:55:07.628251+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "fa5a192e7a1b"
down_revision = "654e34b39c96"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_table("eligibility_parse_record")


def downgrade():
    op.create_table(
        "eligibility_parse_record",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("organization_id", sa.Integer, sa.ForeignKey("organization.id")),
        sa.Column("processing_started_at", sa.DateTime),
        sa.Column("processed_at", sa.DateTime),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("add_count", sa.Integer),
        sa.Column("update_count", sa.Integer),
        sa.Column("delete_count", sa.Integer),
        sa.Column("cannot_delete_count", sa.Integer),
        sa.Column("modified_at", sa.DateTime),
        sa.Column("created_at", sa.DateTime),
        sa.Column("json", sa.Text),
        sa.Column(
            "eligibility_parse_group_id",
            sa.Integer,
            sa.ForeignKey("eligibility_parse_group.id"),
        ),
    )
