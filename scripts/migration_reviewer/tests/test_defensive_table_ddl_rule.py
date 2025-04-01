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
VALID_TABLE_MIGRATION = """
from alembic import op

def upgrade():
    op.execute(
        '''
        IF EXISTS (SELECT * FROM INFORMATION_SCHEMA.TABLES
           WHERE TABLE_NAME='member_health_plan')
        BEGIN
        DROP TABLE `member_health_plan`;
        END;
        '''
    )

def downgrade():
    op.execute(
        '''
        IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.TABLES
           WHERE TABLE_NAME='member_health_plan')
        BEGIN
        CREATE TABLE `member_health_plan` (
            `id` bigint(20) NOT NULL AUTO_INCREMENT,
            `is_family_plan` tinyint(1) DEFAULT NULL
            PRIMARY KEY (`id`),
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        END;
        '''
    )
"""

INVALID_TABLE_MIGRATION = """
from alembic import op

def upgrade():
    op.execute(
        '''
        DROP TABLE `member_health_plan`;
        '''
    )

def downgrade():
    op.execute(
        '''
        ADD TABLE `member_health_plan` (
            `id` bigint(20) NOT NULL AUTO_INCREMENT,
            `is_family_plan` tinyint(1) DEFAULT NULL;
            PRIMARY KEY (`id`),
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        '''
    )
"""


@pytest.mark.parametrize(
    "migration_content,expected_result",
    [(VALID_TABLE_MIGRATION, "success"), (INVALID_TABLE_MIGRATION, "failure")],
)
def test_defensive_sql_scripts_rule(
    migration_content: str, expected_result: str
) -> None:
    """Test defensive SQL scripts rule."""
    # Test data
    migration_files = [{"file": "test_migration.py", "content": migration_content}]
    other_changes = []

    with open("rules/defensive_table_ddl.txt", "r") as f:
        rules = {"defensive_table_ddl.txt": f.read()}

    # Run validation
    results = validate_migrations(migration_files, other_changes, rules)

    assert len(results) == 1
    assert results[0]["rule"] == "defensive_table_ddl.txt"
    assert results[0]["validation_result"] == expected_result
