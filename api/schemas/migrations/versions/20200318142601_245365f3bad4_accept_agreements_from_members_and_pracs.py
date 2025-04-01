"""Accept agreements from members and pracs.

Revision ID: 245365f3bad4
Revises: ae1c878677ba
Create Date: 2020-03-18 14:26:01.566716

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "245365f3bad4"
down_revision = "ae1c878677ba"
branch_labels = None
depends_on = None


def upgrade():
    # Make sure prod foreign_key name matches practitioner_profile_foreign_key
    op.drop_constraint(
        "agreement_acceptance_ibfk_2", "agreement_acceptance", "foreignkey"
    )
    op.alter_column(
        "agreement_acceptance",
        "practitioner_profile_id",
        new_column_name="user_id",
        existing_type=sa.Integer,
        existing_nullable=False,
    )
    op.create_foreign_key(
        "agreement_acceptance_ibfk_2",
        "agreement_acceptance",
        "user",
        ["user_id"],
        ["id"],
    )


def downgrade():
    # Delete acceptances from non-practitioners before going back to only supporting practitioners.
    op.execute(
        "DELETE FROM agreement_acceptance WHERE user_id NOT IN (SELECT user_id FROM practitioner_profile);"
    )
    op.drop_constraint(
        "agreement_acceptance_ibfk_2", "agreement_acceptance", "foreignkey"
    )
    op.alter_column(
        "agreement_acceptance",
        "user_id",
        new_column_name="practitioner_profile_id",
        existing_type=sa.Integer,
        existing_nullable=False,
    )
    op.create_foreign_key(
        "agreement_acceptance_ibfk_2",
        "agreement_acceptance",
        "practitioner_profile",
        ["practitioner_profile_id"],
        ["user_id"],
    )
