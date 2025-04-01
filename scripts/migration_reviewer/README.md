# MigrationReviewer

A tool to automatically validate database migration MRs against predefined rules using LLM-powered analysis.

## Features

- Automatically detects migration changes in merge requests
- Validates changes against customizable rules
- Outputs validation results with detailed explanations in JSON format
- Comments validation results on merge requests
- Easy integration with GitLab CI/CD pipelines

## Installation

### 1. Clone the repository:

```bash
git clone https://gitlab.com/maven-clinic/sandbox/MigrationReviewer.git
cd MigrationReviewer
```

### 2. Install dependencies:

```bash
make bootstrap
```

### 3. Set up your environment variables:

#### 3.1 Local Development
Create a `.env` file in the project root with the following variables:

```bash
GEMINI_API_KEY=your_gemini_api_key_here
GITLAB_TOKEN=your_gitlab_project_access_token
GITLAB_PROJECT_ID=your_gitlab_project_id
```

#### 3.2 How to get GitLab credentials:

1. **GITLAB_PROJECT_ID**:
   - Navigate to your GitLab project's main page
   - The project ID is in the project's Settings -> General -> Project ID

2. **GITLAB_TOKEN**:
   - Go to project's Settings -> Access Tokens
   - Click "Create project access token"
   - Name: `Migration Review Bot`
   - Select scopes: `api`, `write_repository`
   - Click "Create project access token"
   - Copy the token immediately (it won't be shown again)

#### 3.3 GitLab CI/CD Setup
Add the following variables in your GitLab project's CI/CD settings (Settings > CI/CD > Variables):

```bash
GEMINI_API_KEY
GITLAB_TOKEN
GITLAB_PROJECT_ID
```

## Usage

### Running the program
Run the validator on your branch:

```bash
python -m src.migrationreviewer.review
```

Options:
- `--debug`: Print debug information including prompts
- `--migration-scripts-dir`: Specify custom directory for migration scripts (default: "migration_scripts")
- `--mr-id`: GitLab merge request ID to post validation results as a comment

### Running Tests

```bash
pytest  # Run all tests
pytest -v # Run with verbose output
pytest --cov=src # Run tests and show coverage report
pytest tests/test_specific_file.py # Run specific test file
```

### Adding Rules

1. Create a new text file in the `rules` directory
2. Write your rule description in natural language
3. The validator will automatically pick up and apply the new rule
4. Add unit tests to ensure the LLM responds to the new rule as expected

Example rule (`rules/atomicity.txt`):

### Integration with GitLab CI
Refer to `.gitlab-ci.yml` for the integration example.

## Output

### Console Output
The tool provides JSON output with validation results:

```json
{
    "overall_result": "success|failure",
    "rule_results": [
        {
            "rule": "rule_name",
            "validation_result": "success|failure",
            "explanation": "Detailed explanation"
        }
    ]
}
```

### Merge Request Comments
When using the `--mr-id` option, the tool posts a formatted markdown comment on your merge request([example](https://gitlab.com/maven-clinic/sandbox/MigrationReviewer/-/merge_requests/6))

![alt text](mr-comment-screenshot.png)