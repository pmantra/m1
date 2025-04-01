from __future__ import annotations

import os
import sys
from traceback import format_exc

from git import Repo

IGNORE_FLAG = "# noqa"


class DisallowedPatternGroup:
    def __init__(
        self,
        patterns: list[str],
        message: str = "",
        file_extensions: list[str] | None = None,
        exclude_path_patterns: list[str] | None = None,
    ):
        self.patterns = patterns
        self.message = message
        self.file_extensions = file_extensions
        self.exclude_path_patterns = exclude_path_patterns

    def is_not_allowed(
        self,
        line: str,
        file_path: str,
    ) -> bool:
        """
        Checks if the line contains any of the disallowed patterns.
        Returns True if it does, False otherwise.
        """
        if not self.should_check_line(
            line=line,
            file_path=file_path,
        ):
            return False
        found_disallowed_pattern = (
            True if any(pattern in line for pattern in self.patterns) else False
        )
        if found_disallowed_pattern:
            pattern_str = ",".join(self.patterns)
            print(
                f"\nFound disallowed pattern:  (disable check with `{IGNORE_FLAG}`)\n"
                + f"Pattern: [{pattern_str}]\n\n"
                + "Reasoning:\n"
                + f"{self.message}\n\n"
                + f"{file_path}\n"
                + f"{line}\n"
            )
        return found_disallowed_pattern

    def should_check_file_by_extension(
        self,
        file_path: str,
    ) -> bool:
        # match all if no file extensions are provided
        if self.file_extensions is None:
            return True

        for ext in self.file_extensions:
            if file_path.endswith(ext):
                return True  # return on first match
        return False

    def should_check_file_by_excluded_paths(
        self,
        file_path: str,
    ) -> bool:
        # match all if no exclude paths are provided
        if self.exclude_path_patterns is None:
            return True

        for path_pattern in self.exclude_path_patterns:
            if path_pattern in file_path:
                return False
        return True

    def should_check_line(
        self,
        line: str,
        file_path: str,
    ) -> bool:
        """
        Returns a bool indicating if this line should be checked against this
        pattern group.
        """
        if __file__.endswith(file_path):
            # ignore this file
            return False
        if line.startswith("++"):
            return False

        if not self.should_check_file_by_extension(file_path):
            return False

        if not self.should_check_file_by_excluded_paths(file_path):
            return False

        if IGNORE_FLAG in line:
            return False
        return line.startswith("+")


# NOTE: As this list grows it may be worth moving it to a separate file and
# converting it to JSON
disallowed = [
    DisallowedPatternGroup(
        patterns=["datetime.now()", "datetime.datetime.now()", ".now()"],
        message="""[from datetime docs] Warning Because naive datetime objects 
are treated by many datetime methods as local times, it is preferred to use
aware datetimes to represent times in UTC. As such, the recommended way to
create an object representing the current time in UTC is by calling
datetime.now(timezone.utc).

In many cases datetime.utcnow() is acceptable however the resulting datetime
object will be "the current UTC date and time, with tzinfo None."

The guidance is: if you are passing the datetime value out of the scope of its
instantiation, use `datetime.now(timezone.utc)`. If you are only using the
datetime value within the scope of its instantiation, although the above pattern
is preferred, `datetime.utcnow()` is acceptable.

Reference:
https://docs.python.org/3.8/library/datetime.html#datetime.datetime.utcnow""",
        file_extensions=[".py"],
    ),
    DisallowedPatternGroup(
        patterns=["print("],
        message="""Please do not leave stray print()'s hanging around. They are
not JSON formatted and dont properly flow through our log tagging
pipelines. They should only be used in auxiliary scripts.""",
        file_extensions=[".py"],
    ),
    DisallowedPatternGroup(
        patterns=["@threaded_cached_property", "@cached_property"],
        message="""This decorator has been shown to cause unexpected exceptions 
with sqlalchemy's session behavior across threads. If you are looking to add
this to a model property consider these other approaches: 
1. if working with a primitive data type use `primitive_threaded_cached_property`
2. compute it once and store it on a private attribute. 
3. extract the cache implementation to a separate class.""",
        file_extensions=[".py"],
    ),
    DisallowedPatternGroup(
        patterns=["backref="],
        message="""SQLAlchemy's relationship.backref keyword is deprecated.
Use two explicit relationship.back_populates properties instead.
Relationship.back_populates is type-friendly, new-to-sqlalchemy-friendly 
and avoids issues of dynamic generation.
- Read more at: https://docs.sqlalchemy.org/en/14/orm/backref.html""",
    ),
    DisallowedPatternGroup(
        patterns=[
            "MemberHealthPlan.query",
            "query(MemberHealthPlan",
            "EmployerHealthPlan.query",
            "query(EmployerHeathPlan",
        ],
        message="""Please use the HealthPlanRepository instead of querying health plans directly. 
        Using the repository lets us maintain consistent logic around health plan start and end dates.""",
        exclude_path_patterns=[
            "api/wallet/repository/health_plan.py",
            "api/utils/migrations/standardize_subscriber_insurance_id.py",
        ],
    ),
]


def check_for_disallowed_in_diff(
    commit_sha: str, merge_target_branch_name: str
) -> None:
    print(
        f"Checking for disallowed patterns in diff between '{commit_sha}' and '{merge_target_branch_name}' ..."
    )

    # Inferring the repository path from the current directory
    repo_path = os.getcwd()
    repo = Repo(repo_path)

    # Getting the diffs of added lines between the current branch and main branch
    all_diffs = repo.git.diff(
        merge_target_branch_name, commit_sha, unified=1
    ).splitlines()
    # this captures the diff of staged files, only useful for pre-commit
    all_diffs.extend(repo.git.diff("--staged", unified=1).splitlines())

    # Check all disallowed against added lines
    failed = False
    current_file_path = ""
    for line in all_diffs:
        # capture the file path to be displayed in the error message
        if line.startswith("+++"):
            current_file_path = line[6:]
            continue

        for disallowed_pattern_group in disallowed:
            if disallowed_pattern_group.is_not_allowed(
                line=line,
                file_path=current_file_path,
            ):
                failed = True
    print("Diff check complete")
    sys.exit(1 if failed else 0)


try:
    if len(sys.argv) < 2 or len(sys.argv) > 3:
        raise ValueError(
            "Please provide the commit SHA to compare against.\n Usage: python check_disallowed.py <commit_sha> <merge_target_branch_name>"
        )

    commit_sha = sys.argv[1]
    # default to main if not provided
    merge_target_branch_name = "main"
    if len(sys.argv) == 3:
        merge_target_branch_name = sys.argv[2]

    check_for_disallowed_in_diff(
        commit_sha=commit_sha,
        merge_target_branch_name=merge_target_branch_name,
    )
except Exception as e:
    trace = format_exc()
    print(f"Error: {e}\n{trace}")
    sys.exit(1)
