"""Add audit table for FHIR actions

Revision ID: ac0313686a1f
Revises: 7f3f17aab1c6
Create Date: 2021-03-02 18:10:57.330027

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "ac0313686a1f"
down_revision = "7f3f17aab1c6"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "fhir_action",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("type", sa.String(120)),
        sa.Column("target", sa.String(250)),
        sa.Column("user_id", sa.Integer, nullable=True),
        sa.Column("data", sa.Text),
        sa.Column("modified_at", sa.DateTime),
        sa.Column("created_at", sa.DateTime),
    )


def downgrade():
    op.drop_table("fhir_action")
