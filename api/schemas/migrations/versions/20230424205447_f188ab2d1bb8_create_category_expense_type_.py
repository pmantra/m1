"""create_category_expense_type

Revision ID: f188ab2d1bb8
Revises: 4a71df9d4312
Create Date: 2023-04-24 20:54:47.723429+00:00

"""
from alembic import op
import sqlalchemy as sa
import enum

# revision identifiers, used by Alembic.
revision = "f188ab2d1bb8"
down_revision = "4a71df9d4312"
branch_labels = None
depends_on = None


def upgrade():
    class ReimbursementRequestCategoryExpenses(enum.Enum):
        FERTILITY = "FERTILITY"
        ADOPTION = "ADOPTION"
        EGG_FREEZING = "EGG_FREEZING"
        SURROGACY = "SURROGACY"
        CHILDCARE = "CHILDCARE"
        MATERNITY = "MATERNITY"
        MENOPAUSE = "MENOPAUSE"
        PRECONCEPTION_WELLNESS = "PRECONCEPTION_WELLNESS"

    op.create_table(
        "reimbursement_request_category_expense_types",
        sa.Column(
            "reimbursement_request_category_id",
            sa.BigInteger,
            sa.ForeignKey("reimbursement_request_category.id"),
            primary_key=True,
        ),
        sa.Column(
            "expense_type",
            sa.Enum(ReimbursementRequestCategoryExpenses),
            nullable=False,
            primary_key=True,
        ),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("modified_at", sa.DateTime, nullable=False),
    )


def downgrade():
    op.drop_table("reimbursement_request_category_expense_types")
