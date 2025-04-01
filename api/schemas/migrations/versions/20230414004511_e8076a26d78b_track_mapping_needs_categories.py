"""track_mapping_needs_categories

Revision ID: e8076a26d78b
Revises: 4a46e53667cb
Create Date: 2023-04-14 00:45:11.606567+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e8076a26d78b"
down_revision = "4a46e53667cb"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "member_track_need_category",
        sa.Column(
            "track_id",
            sa.Integer,
            sa.ForeignKey("member_track.id"),
            primary_key=True,
        ),
        sa.Column(
            "need_category_id",
            sa.Integer,
            sa.ForeignKey("need_category.id"),
            primary_key=True,
            index=True,
        ),
        sa.Column("created_at", sa.DateTime),
    )

    op.drop_constraint("need_category_ibfk_2", "need_category", type_="foreignkey")
    op.execute(
        "ALTER TABLE need_category MODIFY COLUMN image_id varchar(70) DEFAULT NULL"
    )


def downgrade():
    op.drop_table("member_track_need_category")
    op.execute("ALTER TABLE need_category MODIFY COLUMN image_id int(11) DEFAULT NULL")
    op.create_foreign_key(
        "need_category_ibfk_2",
        "need_category",
        "image",
        ["image_id"],
        ["id"],
    )
