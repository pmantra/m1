"""allow_multiple_invites_of_a_type

Revision ID: ec4381c09d26
Revises: 2188ee5777ff
Create Date: 2022-10-12 15:58:27.712538+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "ec4381c09d26"
down_revision = "2188ee5777ff"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("invite_ibfk_1", "invite", type_="foreignkey")
    op.drop_constraint("uq_user_type", "invite", type_="unique")

    op.create_foreign_key(
        "invite_ibfk_1", "invite", "user", ["created_by_user_id"], ["id"]
    )


def downgrade():
    op.create_unique_constraint(
        constraint_name="uq_user_type",
        table_name="invite",
        columns=["created_by_user_id", "type"],
    )
