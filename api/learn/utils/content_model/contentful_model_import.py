"""
contentful_model_import.py

Import the existing content_model.json to contentful while optionally running a migration

Usage: contentful_model_import.py [--environment=<name>] [--migration [--force] [--script=<script_path>]] [--cross-space-environment-id-override=<id>]

Options:
  -h --help                                     Show this screen.
  --environment=<name>                          Environment (branch) in Contentful to deploy to [default: master]
  --migration                                   Run a python or contentful js migration
  --migration --force                           Always run the migration, even if the content model matches
  --migration --script=<script_path>            Run the specified .js or .py migration script
"""

import filecmp
import importlib
import os
import subprocess
from datetime import datetime

import contentful_management
from docopt import docopt

from learn.utils.content_model.sanitize_contentful_export import sanitize_content_json

# fill these in for the appropriate space
CONTENTFUL_SPACE_ID = os.getenv("CONTENTFUL_LEARN_SPACE_ID", "")
CONTENTFUL_LEARN_MANAGEMENT_KEY = os.getenv("CONTENTFUL_LEARN_MANAGEMENT_KEY", "")
NUMBER_OF_ENVS_ALLOWED = 4

command_prefix = ["contentful", "space"]
space_id = ["--space-id", CONTENTFUL_SPACE_ID]
management_token = ["--mt", CONTENTFUL_LEARN_MANAGEMENT_KEY]

current_directory = os.path.dirname(os.path.abspath(__file__))
expected_content_model_file = os.path.join(current_directory, "content_model.json")
export_dir = "/tmp/learn"


def run_contentful_cmd(
    cmd_and_args: list[str],
    show_stdout: bool = True,
    show_stderr: bool = True,
    exit_on_error: bool = True,
) -> subprocess.CompletedProcess:
    process = subprocess.run(
        [*command_prefix, *cmd_and_args],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if show_stderr:
        print(process.stderr)
    if show_stdout:
        print(process.stdout)
    if exit_on_error and process.returncode != 0:
        exit(process.returncode)
    return process


def compare_content_model(environment: str) -> bool:
    print(
        f"⬅️ Exporting content model from environment {environment} for comparison..."
    )

    exported_file_name = "content_model_new.json"
    exported_content_model_file = os.path.join(export_dir, exported_file_name)
    if not os.path.exists(export_dir):
        os.makedirs(export_dir)

    run_contentful_cmd(
        [
            "export",
            "--environment-id",
            environment,
            "--skip-content",
            "--skip-roles",
            "--skip-webhooks",
            "--content-file",
            exported_content_model_file,
            *space_id,
            *management_token,
        ]
    )

    sanitize_content_json(exported_content_model_file)
    files_are_same = filecmp.cmp(
        expected_content_model_file, exported_content_model_file, shallow=False
    )
    return files_are_same


def delete_lokalise_app_for_environment(environment: str) -> None:
    # When you clone an env, lokalise doesn't play nice with the new one
    try:
        client = contentful_management.Client(CONTENTFUL_LEARN_MANAGEMENT_KEY)
        contentful_environment = client.environments(CONTENTFUL_SPACE_ID).find(
            environment
        )
        # this is (a little) hacky, best to always wrap in a try/catch
        app_id = "70ssKop5SL98q1JOJy3AcA"
        space_id = contentful_environment.sys["space"].id
        result = contentful_environment._client._http_delete(
            f"/spaces/{space_id}/environments/{contentful_environment.name}/app_installations/{app_id}",
            {},
        )
        if result.status_code == 204:
            print(  # noqa
                f"✅ Successfully deleted Lokalise app from environment {environment}"
            )
        elif result.status_code == 404:
            print(f"ℹ️ Lokalise app not found in environment {environment}")  # noqa
        else:
            print(  # noqa
                f"❌ Unexpected status code [{result.status_code}] deleting Loaklise app from {environment}"
            )
    except Exception as e:
        print(  # noqa
            f"❌ Error deleting Lokalise app from environment {environment}: {e}. If the app exists, you should probably delete it manually"
        )


def import_contentful_model(
    environment: str, migration: bool, force: bool, script_path: str
) -> None:
    if not CONTENTFUL_SPACE_ID:
        print("❌ Please set the CONTENTFUL_SPACE_ID variable before continuing")
        exit(1)
    if not CONTENTFUL_LEARN_MANAGEMENT_KEY:
        print(
            "❌ Please set the CONTENTFUL_LEARN_MANAGEMENT_KEY variable before continuing"
        )
        exit(1)

    if not force:
        print(f"🛂 Checking content_model.json against {environment} environment...")
        if compare_content_model(environment):
            print("✋ No changes to update. Goodbye!")
            exit()

    delete_lokalise_app_for_environment(environment)
    if environment == "master":
        print("🧮 Checking if there is room to create a new environment...")
        rows = delete_environment_if_needed()

        new_environment_name = f"master-{datetime.utcnow().strftime('%Y-%m-%d')}"
        if new_environment_name in [row[0] for row in rows]:
            new_environment_name = (
                f"{new_environment_name}_{datetime.utcnow().strftime('%H.%M')}"
            )

        print(
            f"✨ Attempting to create environment {new_environment_name} from master..."
        )
        run_contentful_cmd(
            [
                "environment",
                "create",
                "--environment-id",
                new_environment_name,
                "--name",
                new_environment_name,
                "--source",
                "master",
                "--await-processing",
                *space_id,
                *management_token,
            ]
        )

        print(f"↩️ Attempting to alias environment {new_environment_name} to master...")
        run_contentful_cmd(
            [
                "environment-alias",
                "update",
                "--target-environment-id",
                new_environment_name,
                "--alias-id",
                "master",
                *space_id,
                *management_token,
            ]
        )

        input(
            "🛑 Before continuing, reinstall the Lokalise app on the new master environment: https://www.notion.so/mavenclinic/Re-install-Lokalise-in-Contentful-1d76dff843594933a480b210d725712d?pvs=4.\nThen press any key to continue ... "
        )

    if migration:
        migrations_dir = os.path.join(current_directory, "migrations")
        if script_path:
            current_migration = script_path
        else:
            migrations_files = sorted(
                [
                    file
                    for file in os.listdir(migrations_dir)
                    if file.endswith(".js") or file.endswith(".py")
                ],
                reverse=True,
            )
            current_migration = migrations_files[0]

        if current_migration.endswith(".js"):
            current_migration_filepath = os.path.join(migrations_dir, current_migration)
            print(
                f"🐦 Attempting to run contentful migration from {current_migration} to {environment}..."
            )
            run_contentful_cmd(
                [
                    "migration",
                    current_migration_filepath,
                    "--environment-id",
                    environment,
                    *space_id,
                    *management_token,
                    "--yes",
                ]
            )

            if compare_content_model(environment):
                print(
                    f"🎉 All done! The content model in {environment} matches content_model.json"
                )
                exit()
        else:  # python
            print(
                f"🐦 Attempting to run python migration from {current_migration} to {environment}..."
            )
            python_script = importlib.import_module(
                f"learn.utils.content_model.migrations.{current_migration[:-3]}"
            )
            python_script.do_migration(environment)

    print(f"➡️ Attempting to import content model to {environment}...")
    run_contentful_cmd(
        [
            "import",
            "--environment-id",
            environment,
            "--content-file",
            expected_content_model_file,
            "--content-model-only",
            *space_id,
            *management_token,
        ]
    )

    print("🛂 Will now check the new content model...")
    if compare_content_model(environment):
        print(
            f"🎉 All done! The content model in {environment} matches content_model.json"
        )
    else:
        print(
            f"😓 Oh no! The content model in {environment} doesn't match content_model.json"
        )


def delete_environment_if_needed() -> list[list[str]]:
    get_environments = run_contentful_cmd(
        ["environment", "list", *space_id, *management_token],
        show_stdout=False,
    )
    # parsing environments
    rows = [
        [item.strip() for item in row.split("│") if item]
        for row in get_environments.stdout.split("\n")[4::2]
        if row
    ]
    if len(rows) == NUMBER_OF_ENVS_ALLOWED + 1:
        # they print an extra for the alias. we really only can have 4 environments
        print(
            f"🧹 {NUMBER_OF_ENVS_ALLOWED} environments already exist. Let's find one to delete"
        )

        # the currently active master looks like "master-2022-06-09 [active]"
        master_env = [row[0] for row in rows if row[1] == "master"][0][:-9]
        inactive_master_envs = [
            row[0]
            for row in rows
            if "[active]" not in row[0] and row[0] != master_env and "master" in row[0]
        ]

        not_qa_or_master_envs = [
            row[0] for row in rows if "master" not in row[0] and row[0] != "qa"
        ]

        if len(not_qa_or_master_envs) > 0:
            print("The following non-master environment(s) exist:")
            [print(f"• {env}") for env in not_qa_or_master_envs]

        if len(inactive_master_envs) > 0:
            print("The following master backup environment(s) exist:")
            [print(f"• {env}") for env in inactive_master_envs]

        env_to_delete = input("Which environment would you like to delete?")
        if env_to_delete not in [*not_qa_or_master_envs, *inactive_master_envs]:
            print(
                f"⛔ {env_to_delete} is not eligible to be deleted. Run script again to try another one."
            )
            exit(1)

        print(f"🗑️ Attempting to delete environment {env_to_delete}...")
        run_contentful_cmd(
            [
                "environment",
                "delete",
                "--environment-id",
                env_to_delete,
                *space_id,
                *management_token,
            ]
        )
    return rows


if __name__ == "__main__":
    # contentful CLI is using chalk to color the terminal which was messing with our parsing
    # this disables the coloring https://github.com/chalk/supports-color/pull/31
    os.environ["FORCE_COLOR"] = "0"
    args = docopt(__doc__)
    import_contentful_model(
        environment=args["--environment"],
        migration=args["--migration"],
        force=args["--migration"] and args["--force"],
        script_path=args["--script"] if args["--migration"] else None,
    )
