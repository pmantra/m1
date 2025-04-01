"""persist Snowflake tables

Revision ID: 115645387a0f
Revises: 24d24e7847f1
Create Date: 2022-09-02 15:22:36.661407+00:00

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "115645387a0f"
down_revision = "24d24e7847f1"
branch_labels = None
depends_on = None

from models import enterprise, questionnaires
from wallet.models import reimbursement_wallet_dashboard


def get_snowflake_time_logged_tables():
    return [
        enterprise.OrganizationModuleExtension,
        enterprise.UserAsset,
        reimbursement_wallet_dashboard.ReimbursementWalletDashboard,
        reimbursement_wallet_dashboard.ReimbursementWalletDashboardCard,
    ]


def get_base_snowflake_tables():
    return [
        questionnaires.Answer,
        questionnaires.Question,
        questionnaires.Questionnaire,
        questionnaires.QuestionSet,
        questionnaires.RecordedAnswer,
        questionnaires.RecordedAnswerSet,
    ]


def upgrade():
    for snowflake_table in get_snowflake_time_logged_tables():
        op.add_column(
            snowflake_table.__tablename__, sa.Column("created_at", sa.DateTime)
        )

    for base_snowflake_table in get_base_snowflake_tables():
        op.add_column(
            base_snowflake_table.__tablename__,
            sa.Column("created_at", sa.DateTime, nullable=True),
        )
        op.add_column(
            base_snowflake_table.__tablename__,
            sa.Column("modified_at", sa.DateTime, nullable=True),
        )


def downgrade():
    for snowflake_table in get_snowflake_time_logged_tables():
        op.drop_column(snowflake_table.__tablename__, "created_at")

    for base_snowflake_table in get_base_snowflake_tables():
        op.drop_column(base_snowflake_table.__tablename__, "created_at")
        op.drop_column(base_snowflake_table.__tablename__, "modified_at")
