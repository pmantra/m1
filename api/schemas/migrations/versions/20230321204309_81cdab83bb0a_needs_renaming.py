"""needs-renaming

Revision ID: 81cdab83bb0a
Revises: e33216ee8b6e
Create Date: 2023-03-21 20:43:09.263382+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "81cdab83bb0a"
down_revision = "e33216ee8b6e"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("needs_category_ibfk_1", "needs_category", type_="foreignkey")
    op.create_foreign_key(
        "needs_category_ibfk_1",
        "needs_category",
        "need_categories",
        ["category_id"],
        ["id"],
    )

    op.execute("ALTER TABLE needs_category CHANGE needs_id need_id int(11) NOT NULL;")
    op.execute("ALTER TABLE needs_specialty CHANGE needs_id need_id int(11) NOT NULL;")
    op.execute(
        "ALTER TABLE needs_specialty_keyword CHANGE needs_id need_id int(11) NOT NULL;"
    )
    op.execute("ALTER TABLE needs_vertical CHANGE needs_id need_id int(11) NOT NULL;")

    op.execute("RENAME TABLE `needs` TO `need`;")
    op.execute("RENAME TABLE `needs_category` TO `need_need_category`;")
    op.execute("RENAME TABLE `need_categories` TO `need_category`;")
    op.execute("RENAME TABLE `needs_specialty` TO `need_specialty`;")
    op.execute("RENAME TABLE `needs_specialty_keyword` TO `need_specialty_keyword`;")
    op.execute("RENAME TABLE `needs_vertical` TO `need_vertical`;")


def downgrade():
    op.execute("RENAME TABLE `need` TO `needs`;")
    op.execute("RENAME TABLE `need_need_category` TO `needs_category`;")
    op.execute("RENAME TABLE `need_category` TO `need_categories`;")
    op.execute("RENAME TABLE `need_specialty` TO `needs_specialty`;")
    op.execute("RENAME TABLE `need_specialty_keyword` TO `needs_specialty_keyword`;")
    op.execute("RENAME TABLE `need_vertical` TO `needs_vertical`;")

    op.execute("ALTER TABLE needs_category CHANGE need_id needs_id int(11) NOT NULL;")
    op.execute("ALTER TABLE needs_specialty CHANGE need_id needs_id int(11) NOT NULL;")
    op.execute(
        "ALTER TABLE needs_specialty_keyword CHANGE need_id needs_id int(11) NOT NULL;"
    )
    op.execute("ALTER TABLE needs_vertical CHANGE need_id needs_id int(11) NOT NULL;")
