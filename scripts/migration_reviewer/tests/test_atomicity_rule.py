import pytest
from dotenv import load_dotenv
from src.migrationreviewer.review import genai, validate_migrations
from src.migrationreviewer.settings import MigrationReviewerSettings

# Load environment variables
load_dotenv()
config = MigrationReviewerSettings.from_environ()
api_key = config.gemini_api_key
genai.configure(api_key=api_key, transport="rest")

# Sample migration scripts for testing
ATOMIC_MIGRATION = """
from alembic import op

def upgrade():
    op.execute(
        '''
        BEGIN;
        ALTER TABLE `member_health_plan`
        CHANGE COLUMN `is_family_plan` `deprecated_is_family_plan` tinyint(1) DEFAULT NULL;
        ALTER TABLE `patient_appointment`
        ADD COLUMN `deprecated_appointment_type` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL;
        COMMIT;
        '''
    )

def downgrade():
    op.execute(
        '''
        BEGIN;
        ALTER TABLE `member_health_plan`
        CHANGE COLUMN `deprecated_is_family_plan` `is_family_plan` tinyint(1) DEFAULT NULL;
        ALTER TABLE `patient_appointment`
        DROP COLUMN `deprecated_appointment_type`;
        COMMIT;
        '''
    )
"""

NON_ATOMIC_MIGRATION = """
from alembic import op

def upgrade():
    op.execute('''
        ALTER TABLE `member_health_plan`
        CHANGE COLUMN `is_family_plan` `deprecated_is_family_plan` varchar(50) DEFAULT NULL;

        ALTER TABLE `patient_appointment`
        ADD COLUMN `deprecated_appointment_type` varchar(50) DEFAULT NULL;
    ''')

def downgrade():
    op.execute('''
        ALTER TABLE `member_health_plan`
        CHANGE COLUMN `deprecated_is_family_plan` `is_family_plan` varchar(50) DEFAULT NULL;

        ALTER TABLE `patient_appointment`
        DROP COLUMN `deprecated_appointment_type`;
    ''')
"""


@pytest.mark.parametrize(
    "migration_content,expected_result",
    [(ATOMIC_MIGRATION, "success"), (NON_ATOMIC_MIGRATION, "failure")],
)
def test_atomicity_rule(migration_content: str, expected_result: str) -> None:
    """Test the atomicity rule."""
    # Test data
    migration_files = [{"file": "test_migration.py", "content": migration_content}]
    other_changes = []

    with open("rules/atomicity.txt", "r") as f:
        rules = {"atomicity.txt": f.read()}

    # Run validation
    results = validate_migrations(migration_files, other_changes, rules)

    assert len(results) == 1
    assert results[0]["rule"] == "atomicity.txt"
    assert results[0]["validation_result"] == expected_result
