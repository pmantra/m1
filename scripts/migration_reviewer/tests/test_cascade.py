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
CASCADE_MIGRATION = """
from alembic import op

def upgrade():
    op.execute(
        '''
        BEGIN;
        CREATE TABLE Persons (
            id int NOT NULL,
            Age int,
            FOREIGN KEY (id) REFERENCES Authors(id) ON DELETE CASCADE,
             /* We do not need ON UPDATE CASCADE here */
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

NON_CASCADE_MIGRATION = """
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

NON_CASCADE_WITH_COMMENT_MIGRATION = """
from alembic import op

def upgrade():
    op.execute(
        '''
        /* We do not need CASCADE due to single use table */
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
    [
        (CASCADE_MIGRATION, "success"),
        (NON_CASCADE_MIGRATION, "failure"),
        (NON_CASCADE_WITH_COMMENT_MIGRATION, "success"),
    ],
)
def test_cascade_rule(migration_content: str, expected_result: str) -> None:
    """Test the atomicity rule."""
    # Test data
    migration_files = [{"file": "test_migration.py", "content": migration_content}]
    other_changes = []

    with open("rules/cascade.txt", "r") as f:
        rules = {"cascade.txt": f.read()}

    # Run validation
    results = validate_migrations(migration_files, other_changes, rules)

    assert len(results) == 1
    assert results[0]["rule"] == "cascade.txt"
    assert results[0]["validation_result"] == expected_result
