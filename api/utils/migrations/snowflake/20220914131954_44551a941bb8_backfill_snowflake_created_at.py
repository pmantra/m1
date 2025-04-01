"""backfill Snowflake created_at

Revision ID: 44551a941bb8
Revises: 80f6621df164
Create Date: 2022-09-14 13:19:54.716796+00:00

"""
from alembic import op

from authn.models import sso
from models import enterprise, gdpr, questionnaires
from models.tracks import assessment
from storage.connection import db
from wallet.models import (
    reimbursement,
    reimbursement_organization_settings,
    reimbursement_request_source,
    reimbursement_wallet,
    reimbursement_wallet_dashboard,
    reimbursement_wallet_debit_card,
)

# revision identifiers, used by Alembic.
revision = "44551a941bb8"
down_revision = "c3907b62ef6f"
branch_labels = None
depends_on = None

NUM_CHUNKS = 10


def get_backfill_table_list():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    return [
        sso.ExternalIdentity,
        enterprise.OrganizationModuleExtension,
        enterprise.UserAsset,
        gdpr.GDPRUserRequest,
        questionnaires.Answer,
        questionnaires.Question,
        questionnaires.Questionnaire,
        questionnaires.QuestionSet,
        questionnaires.RecordedAnswer,
        questionnaires.RecordedAnswerSet,
        assessment.AssessmentTrack,
        reimbursement.ReimbursementAccount,
        reimbursement.ReimbursementAccountType,
        reimbursement.ReimbursementClaim,
        reimbursement.ReimbursementPlan,
        reimbursement.ReimbursementPlanCoverageTier,
        reimbursement.ReimbursementRequest,
        reimbursement.ReimbursementRequestCategory,
        reimbursement.ReimbursementRequestExchangeRates,
        reimbursement.ReimbursementTransaction,
        reimbursement.ReimbursementTransaction,
        reimbursement.ReimbursementWalletPlanHDHP,
        reimbursement_organization_settings.ReimbursementOrganizationSettings,
        reimbursement_organization_settings.ReimbursementOrgSettingCategoryAssociation,
        reimbursement_request_source.ReimbursementRequestSource,
        reimbursement_wallet.ReimbursementWallet,
        reimbursement_wallet_dashboard.ReimbursementWalletDashboard,
        reimbursement_wallet_dashboard.ReimbursementWalletDashboardCard,
        reimbursement_wallet_debit_card.ReimbursementWalletDebitCard,
    ]


def update_table(table_name):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    # Get initial ID

    max_id = db.session.execute(
        f"SELECT MAX(id) FROM {table_name} WHERE created_at IS NULL"
    ).fetchall()[0][0]
    min_id = db.session.execute(
        f"SELECT MIN(id) FROM {table_name} WHERE created_at IS NULL"
    ).fetchall()[0][0]

    # Only run upgrade if there are things to add
    if max_id and min_id:
        size_diff = max_id - min_id

        if size_diff == 0 or size_diff < NUM_CHUNKS:
            range_list = [min_id]
        else:
            chunk_size = round(size_diff / NUM_CHUNKS)
            range_list = list(range(min_id, max_id, chunk_size))

        # Get 1 higher than the max ID to ensure the highest value is updated
        range_list.append(max_id + 1)

        for i, num in enumerate(range_list[:-1]):
            chunk_min = num
            chunk_max = range_list[i + 1]
            update_chunk(table_name=table_name, start_id=chunk_min, end_id=chunk_max)


def update_chunk(table_name, start_id, end_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    # 1388534400 Seconds in UNIX time is 2014-01-01 (Snowflake start time)
    # and ID is the creation time bitwise shifted per Snowflake logic
    chunk_statement = (
        f"UPDATE {table_name} SET created_at = FROM_UNIXTIME((1388534400 + ((id >> 22) / 1000))) "
        f"WHERE id >= {start_id} and id < {end_id}"
    )
    op.execute(chunk_statement)


def upgrade():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    for table in get_backfill_table_list():
        update_table(table_name=table.__tablename__)


def downgrade():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    for table in get_backfill_table_list():
        op.execute(f"UPDATE {table.__tablename__} SET created_at = NULL")
