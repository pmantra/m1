"""add_language_id_to_agreement_table

Revision ID: 4a71df9d4312
Revises: 02890648bca4
Create Date: 2023-04-26 15:37:32.316449+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "4a71df9d4312"
down_revision = "02890648bca4"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "agreement",
        sa.Column(
            "language_id",
            sa.Integer,
            sa.ForeignKey("language.id", ondelete="CASCADE", onupdate="CASCADE"),
            nullable=True,
        ),
    )


def downgrade():
    op.drop_constraint("agreement_ibfk_1", "agreement", type_="foreignkey")
    op.drop_column("agreement", "language_id")
