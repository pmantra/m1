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
PK_MIGRATION = """
from alembic import op

def upgrade():
    op.execute(
        '''
        BEGIN;
        CREATE TABLE Persons (
            id int NOT NULL,
            Age int,
            created_at timestamp default current_timestamp,
            modified_at timestamp default current_timestamp,
            PRIMARY KEY (id)
        );
        COMMIT;
        '''
    )

def downgrade():
    op.execute(
        '''
        BEGIN;
        DROP TABLE Persons;
        COMMIT;
        '''
    )
"""

NON_PK_MIGRATION = """
from alembic import op

def upgrade():
    op.execute(
        '''
        BEGIN;
        CREATE TABLE Persons (
            id int NOT NULL,
            Age int,
            PRIMARY KEY (id)
        );
        COMMIT;
        '''
    )

def downgrade():
    op.execute(
        '''
        BEGIN;
        DROP TABLE Persons;
        COMMIT;
        '''
    )
"""


@pytest.mark.parametrize(
    "migration_content,expected_result",
    [(PK_MIGRATION, "success"), (NON_PK_MIGRATION, "failure")],
)
def test_timestamp_rule(migration_content: str, expected_result: str) -> None:
    """Test the atomicity rule."""
    # Test data
    migration_files = [{"file": "test_migration.py", "content": migration_content}]
    other_changes = []

    with open("rules/table_timestamp.txt", "r") as f:
        rules = {"table_timestamp.txt": f.read()}

    # Run validation
    results = validate_migrations(migration_files, other_changes, rules)

    assert len(results) == 1
    assert results[0]["rule"] == "table_timestamp.txt"
    assert results[0]["validation_result"] == expected_result
