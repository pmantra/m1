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
INSTANT_MIGRATION = """
from alembic import op

def upgrade():
    op.execute(
        '''
        BEGIN;
        ALTER TABLE `member_health_plan` RENAME COLUMN `is_family_plan` to `new_is_family_plan`, ALGORITHM=INSTANT;
        ALTER TABLE `member_health_plan` ALTER `new_is_family_plan` SET DEFAULT 'test', ALGORITHM=INSTANT;
        ALTER TABLE `member_health_plan` ADD `test_data` tinyint(1) NULL, ALGORITHM=INSTANT;
        COMMIT;
        '''
    )

def downgrade():
    op.execute(
        '''
        BEGIN;
        ALTER TABLE `member_health_plan` RENAME COLUMN `new_is_family_plan` to `is_family_plan`, ALGORITHM=INSTANT;
        ALTER TABLE `member_health_plan` ALTER `new_is_family_plan` DROP DEFAULT, ALGORITHM=INSTANT;
        ALTER TABLE `member_health_plan` DROP COLUMN `test_data`, ALGORITHM=INSTANT;
        COMMIT;
        '''
    )
"""

NON_INSTANT_MIGRATION = """
from alembic import op

def upgrade():
    op.execute(
        '''
        BEGIN;
        ALTER TABLE `member_health_plan` RENAME COLUMN `is_family_plan` to `new_is_family_plan`;
        ALTER TABLE `member_health_plan` ALTER `new_is_family_plan` SET DEFAULT 'test';
        ALTER TABLE `member_health_plan` ADD `test_data` tinyint(1) NULL;
        COMMIT;
        '''
    )

def downgrade():
    op.execute(
        '''
        BEGIN;
        ALTER TABLE `member_health_plan` RENAME COLUMN `new_is_family_plan` to `is_family_plan`;
        ALTER TABLE `member_health_plan` ALTER `new_is_family_plan` DROP DEFAULT;
        ALTER TABLE `member_health_plan` DROP COLUMN `test_data`;
        COMMIT;
        '''
    )
"""


@pytest.mark.parametrize(
    "migration_content,expected_result",
    [(INSTANT_MIGRATION, "success"), (NON_INSTANT_MIGRATION, "failure")],
)
def test_algorithm_instant_rule(migration_content: str, expected_result: str) -> None:
    """Test the atomicity rule."""
    # Test data
    migration_files = [{"file": "test_migration.py", "content": migration_content}]
    other_changes = []

    with open("rules/instant_metadata_changes.txt", "r") as f:
        rules = {"instant_metadata_changes.txt": f.read()}

    # Run validation
    results = validate_migrations(migration_files, other_changes, rules)

    assert len(results) == 1
    assert results[0]["rule"] == "instant_metadata_changes.txt"
    assert results[0]["validation_result"] == expected_result
