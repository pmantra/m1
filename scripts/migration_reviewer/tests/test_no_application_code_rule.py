import pytest
from dotenv import load_dotenv
from src.migrationreviewer.review import genai, validate_migrations
from src.migrationreviewer.settings import MigrationReviewerSettings

# Load environment variables
load_dotenv()
config = MigrationReviewerSettings.from_environ()
api_key = config.gemini_api_key
genai.configure(api_key=api_key, transport="rest")

# Sample migrations for testing application code changes
VALID_MIGRATION = """
from alembic import op

def upgrade():
    op.execute('''
        ALTER TABLE users
        ADD COLUMN email VARCHAR(255);
    ''')

def downgrade():
    op.execute('''
        ALTER TABLE users
        DROP COLUMN email;
    ''')
"""

VALID_OTHER_CHANGES = [
    {"file": "migrations/versions/123456_add_email_column.py", "diff": VALID_MIGRATION}
]

INVALID_OTHER_CHANGES = [
    {"file": "migrations/versions/123456_add_email_column.py", "diff": VALID_MIGRATION},
    {
        "file": "app/models/user.py",
        "diff": """
@@ -1,6 +1,13 @@
 class User(db.Model):
     id = db.Column(db.Integer, primary_key=True)
+    email = db.Column(db.String(255))  # New field added
+
+    def send_welcome_email(self):
+        # Application code changes
+        email_service = EmailService()
+        email_service.send_welcome_email(self.email)
""",
    },
    {
        "file": "app/services/email_service.py",
        "diff": """
@@ -0,0 +1,6 @@
+class EmailService:
+    def send_welcome_email(self, email):
+        # New application code
+        template = EmailTemplate.get('welcome')
+        send_email(email, template)
""",
    },
]


@pytest.mark.parametrize(
    "migration_content,other_changes,expected_result",
    [
        (VALID_MIGRATION, VALID_OTHER_CHANGES, "success"),
        (VALID_MIGRATION, INVALID_OTHER_CHANGES, "failure"),
    ],
)
def test_no_application_code_rule(
    migration_content: str, other_changes: str, expected_result: str
) -> None:
    """Test that the MR doesn't contain application code changes."""
    # Test data
    migration_files = [
        {
            "file": "migrations/versions/123456_add_email_column.py",
            "content": migration_content,
        }
    ]

    with open("rules/no_application_code_changes.txt", "r") as f:
        rules = {"no_application_code_changes.txt": f.read()}

    # Run validation
    results = validate_migrations(migration_files, other_changes, rules)

    assert len(results) == 1
    assert results[0]["rule"] == "no_application_code_changes.txt"
    assert results[0]["validation_result"] == expected_result
