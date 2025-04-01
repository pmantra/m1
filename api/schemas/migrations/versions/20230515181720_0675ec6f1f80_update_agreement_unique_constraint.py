"""update_agreement_unique_constraint

Revision ID: 0675ec6f1f80
Revises: be652872e1c3
Create Date: 2023-05-15 18:17:20.227828+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "0675ec6f1f80"
down_revision = "f4ece4e2ffdb"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("agreement") as batch_op:
        batch_op.drop_constraint("uq_version_name", type_="unique")
        batch_op.create_unique_constraint(
            "uq_version_name_language",
            ["version", "name", "language_id"],
        )


def downgrade():
    with op.batch_alter_table("agreement") as batch_op:
        batch_op.drop_constraint("uq_version_name_language", type_="unique")
        batch_op.create_unique_constraint(
            "uq_version_name",
            ["version", "name"],
        )
