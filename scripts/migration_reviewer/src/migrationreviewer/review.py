import json
import os
import subprocess

import google.generativeai as genai
from dotenv import load_dotenv
from src.migrationreviewer.gitlab_client import GitLabClient, format_validation_results
from src.migrationreviewer.settings import MigrationReviewerSettings

load_dotenv()  # load the API key from .env file
config = MigrationReviewerSettings.from_environ()
api_key = config.gemini_api_key

genai.configure(api_key=api_key, transport="rest")
model = genai.GenerativeModel(
    "gemini-2.0-flash", generation_config={"response_mime_type": "application/json"}
)


def get_mr_changes(migration_scripts_dir="api/schemas/migrations/versions"):  # type: ignore[no-untyped-def]
    """Get all files and their diffs in current branch compared to main"""
    from pathlib import Path

    current_folder = Path.cwd()
    parent_folder = os.path.dirname(current_folder)
    repo_folder = os.path.dirname(parent_folder)

    try:
        # First fetch the main branch to ensure it's available
        subprocess.run(["git", "fetch", "origin", "main", "--depth=1"], check=True)

        # Get list of changed files
        files_cmd = ["git", "diff", "--name-only", "FETCH_HEAD", "HEAD"]
        files_result = subprocess.run(
            files_cmd, capture_output=True, text=True, check=True
        )

        # Categorize files and get their diffs
        changes = {"migration_files": [], "other_changes": []}
        # SQL files under the dump folder is for local development
        # We can skip them from any analysis
        skip_dump_folder = "api/schemas/dump/"

        for file in files_result.stdout.splitlines():
            if file.startswith(f"{migration_scripts_dir}/") and file.endswith(".py"):
                file_name = f"{repo_folder}/{file}"
                # For migration files, read the entire current file content
                try:
                    with open(file_name, "r") as f:
                        file_content = f.read()
                    changes["migration_files"].append(
                        {
                            "file": file,
                            "content": file_content,  # Store full content instead of diff
                        }
                    )
                except FileNotFoundError:
                    print(f"Warning: Migration file {file_name} not found")  # noqa
                    continue
            elif file.startswith(f"{skip_dump_folder}"):
                continue
            else:
                # For other files, keep the diff as before
                diff_cmd = ["git", "diff", "FETCH_HEAD", "HEAD", "--", file]
                diff_result = subprocess.run(
                    diff_cmd, capture_output=True, text=True, check=True
                )
                changes["other_changes"].append(
                    {"file": file, "diff": diff_result.stdout}
                )

        return changes
    except subprocess.CalledProcessError as e:
        print(f"Error getting changed files: {e}")  # noqa
        exit(1)


def load_rules(rules_dir="rules"):  # type: ignore[no-untyped-def]
    """Load all rules from the rules directory"""
    rules = {}
    for filename in os.listdir(rules_dir):
        if filename.endswith(".txt"):
            with open(os.path.join(rules_dir, filename), "r") as file:
                rules[filename] = file.read()
    return rules


def validate_migrations(migration_files, other_changes, rules, debug=False):  # type: ignore[no-untyped-def]
    """Validate all migration files against rules in a single LLM call"""
    results = []

    for rule_name, rule_content in rules.items():
        prompt = f"""
        Please analyze these migration script changes:

        Migration Files:
        {format_migration_files(migration_files)}

        Other changes in the MR:
        {format_other_changes(other_changes)}

        Rule:
        {rule_content}

        The response should be in json format like this:
        {{
          "validation_result": <"success"|"failure">,
          "explanation": <explanation of why the validation succeeded or failed>
        }}
        """

        if debug:
            print(f"\n=== Prompt for {rule_name} ===")  # noqa
            print(prompt)  # noqa
            print("=== End Prompt ===\n")  # noqa

        analysis_result = model.generate_content(prompt)
        validation = json.loads(analysis_result.text)
        rule_result = {
            "rule": rule_name,
            "validation_result": validation["validation_result"],
            "explanation": validation["explanation"],
        }
        results.append(rule_result)

    return results


def format_migration_files(migration_files):  # type: ignore[no-untyped-def]
    """Format all migration files for the prompt"""
    return "\n\n".join(
        f"File: {migration['file']}\nContent:\n{migration['content']}"  # Changed from diff to content
        for migration in migration_files
    )


def format_other_changes(other_changes):  # type: ignore[no-untyped-def]
    """Format other changes for the prompt"""
    return "\n\n".join(
        f"File: {change['file']}\nChanges:\n{change['diff']}"
        for change in other_changes
    )


def main():  # type: ignore[no-untyped-def]
    import argparse

    parser = argparse.ArgumentParser(
        description="Validate migration files against rules"
    )
    parser.add_argument(
        "--debug", action="store_true", help="Print debug information including prompts"
    )
    parser.add_argument(
        "--migration-scripts-dir",
        default="api/schemas/migrations/versions",
        help='Directory containing migration scripts (default: "/api/schemas/migrations/versions")',
    )
    parser.add_argument("--mr-id", help="GitLab merge request ID to post results to")
    args = parser.parse_args()

    # Get all changed files and their diffs
    if args.debug:
        print("Getting changed files...")  # noqa
    changes = get_mr_changes(args.migration_scripts_dir)

    if not changes["migration_files"]:
        print("No migration files to validate")  # noqa
        exit(0)

    if args.debug:
        print(  # noqa
            f"Found {len(changes['migration_files'])} migration files and {len(changes['other_changes'])} other changes"
        )

    # Load all rules
    rules = load_rules()
    if args.debug:
        print(f"Loaded {len(rules)} rules")  # noqa

    # Validate all migration files at once
    validation_results = validate_migrations(
        changes["migration_files"], changes["other_changes"], rules, args.debug
    )

    # Post results to GitLab if MR ID is provided
    if args.mr_id:
        try:
            gitlab_client = GitLabClient(
                config.gitlab_token, config.gitlab_project_id, config.gitlab_url
            )
            markdown_comment = format_validation_results(validation_results)
            if gitlab_client.post_mr_comment(args.mr_id, markdown_comment):
                print("Successfully posted results to GitLab MR")  # noqa
            else:
                print("Failed to post results to GitLab MR")  # noqa
        except ValueError as e:
            print(f"GitLab configuration error: {e}")  # noqa

    # Display JSON results
    aggregated_result = {
        "overall_result": (
            "success"
            if all(r["validation_result"] == "success" for r in validation_results)
            else "failure"
        ),
        "rule_results": validation_results,
    }

    print(json.dumps(aggregated_result, indent=4))  # noqa


if __name__ == "__main__":
    main()
