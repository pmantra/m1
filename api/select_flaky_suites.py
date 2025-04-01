import json
import os
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from itertools import chain
from typing import Dict, List, cast


@dataclass
class TestGroup:
    suites: List[str] = field(default_factory=list)
    duration: float = 0.0


def main(durations_path: str, flaky_tests: List[str], group: int, splits: int) -> None:

    groups = [TestGroup() for _ in range(splits)]

    # Calculate expected duration per suite:
    durations = load_test_durations(durations_path)
    # Assume test collection for a suite takes about 20s
    suite_durations = defaultdict(lambda: 20.0)
    for test in flaky_tests:
        suite = test.split("/")[0]
        # Assume each test takes 1s if we don't have performance data
        duration = durations.get(test, 1.0)
        # print(f"{suite}\t{duration}\t{test}")  # noqa
        suite_durations[suite] += duration

    # Calculate the average duration per group:
    avg_per_group = sum(suite_durations.values()) / splits

    # Pack suites (from longest to shortest) into groups while staying under the avg per group
    suites = iter(
        sorted(
            suite_durations.items(),
            reverse=True,
            key=lambda item: item[1],
        )
    )
    idx = 0
    try:
        for suite, s_duration in suites:
            while (g := groups[idx]).duration + s_duration > avg_per_group:
                idx += 1
            g.suites.append(suite)
            g.duration += s_duration
    except IndexError:
        # The current suite still needs to be assigned
        suites = chain([(suite, s_duration)], suites)

    # Pack remaining suites into groups from least assigned to most assigned
    for suite, s_duration in suites:
        min_group = min(groups, key=lambda g: g.duration)
        min_group.suites.append(suite)
        min_group.duration += s_duration

    print(" ".join(groups[group - 1].suites))  # noqa
    return None


def load_test_durations(durations_path: str) -> Dict[str, float]:
    try:
        with open(durations_path, "r") as f:
            durations = json.load(f)
            return cast(Dict[str, float], durations)
    except (FileNotFoundError, ValueError) as e:
        print(f"Unable to load {durations_path}: {e}", file=sys.stderr)  # noqa
        return {}


def _get_int(name) -> int:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    val = os.getenv(name)
    if val is None:
        raise ValueError(f"Expected env var {name} to be set.")
    return int(val)


if __name__ == "__main__":
    try:
        durations_path = sys.argv[1]
    except IndexError:
        durations_path = ".test_durations"

    # pytest --collect-only -m flaky_in_splits -q | python -m select_flaky_suites
    flaky_tests: List[str] = []
    for line in sys.stdin:
        if not (line := line.rstrip()):
            break
        flaky_tests.append(line)

    main(
        durations_path=durations_path,
        flaky_tests=flaky_tests,
        group=int(_get_int("CI_NODE_INDEX")),
        splits=int(_get_int("CI_NODE_TOTAL")),
    )
