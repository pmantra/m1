"""BEX-5187_1_of_n_key_update

Revision ID: 2aed10582284
Revises: ff4299401028
Create Date: 2024-11-11 17:23:11.025471+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "2aed10582284"
down_revision = "ff4299401028"
branch_labels = None
depends_on = None


def upgrade():
    # First migration: Drop the old key
    sql_drop_key = """
        ALTER TABLE maven.`annual_insurance_questionnaire_response` 
        DROP KEY `uk_wallet_id_survey_year`,
        ALGORITHM=COPY, 
        LOCK=SHARED;
    """
    op.execute(sql_drop_key)

    # Second migration: Add the new key
    sql_add_key = """
        ALTER TABLE maven.`annual_insurance_questionnaire_response`
        ADD UNIQUE KEY `uk_wallet_id_survey_year_user_id` 
        (`wallet_id`, `survey_year`, `submitting_user_id`),
        ALGORITHM=COPY, 
        LOCK=SHARED;
    """
    op.execute(sql_add_key)


def downgrade():
    # First migration: Drop the new key
    sql_drop_new_key = """
        ALTER TABLE maven.`annual_insurance_questionnaire_response`
        DROP KEY `uk_wallet_id_survey_year_user_id`,
        ALGORITHM=COPY, 
        LOCK=SHARED;
    """
    op.execute(sql_drop_new_key)

    # Second migration: Restore the original key
    sql_restore_key = """
        ALTER TABLE maven.`annual_insurance_questionnaire_response`
        ADD UNIQUE KEY `uk_wallet_id_survey_year` 
        (`wallet_id`, `survey_year`),
        ALGORITHM=COPY, 
        LOCK=SHARED;
    """
    op.execute(sql_restore_key)
