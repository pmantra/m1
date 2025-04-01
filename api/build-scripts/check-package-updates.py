#!/usr/bin/env python3
from collections import namedtuple
from itertools import islice
from sys import exit, stdin

Version = namedtuple("Version", ["major", "minor", "patch"], defaults=[0, 0])


MAJOR_TOLERANCE = 11  # marshmallow and flask
MINOR_TOLERANCE = 24  # eventually


def parse_version(version):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    components = tuple(
        islice((int(v) for v in version.split(".")), 3)
    )  # ignore past the third component
    return Version(*components)


def print_alerts(alerts):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    for package, used, available in alerts:
        print(f"  {package} {used} ({available})")


def main() -> None:
    """Expects the output of yolk -U from stdin.

    Example Inputs:

        Flask 0.12.4 (1.1.1)
        Jinja2 2.10 (2.10.3)
        billiard 3.5.0.3 (3.6.1.0)
        click 6.7 (7.0)
        pytz 2018.3 (2019.3)
        regex 2019.1.24 (2019.08.19)
    """
    parse_errors = []
    major_alerts = []
    minor_alerts = []
    patch_alerts = []
    for line in map(str.rstrip, stdin):
        try:
            package_name, used_str, available_str = line.split(" ")
            available_str = available_str.lstrip("(").rstrip(")")
            used = parse_version(used_str)
            available = parse_version(available_str)
            alert = (package_name, used_str, available_str)
            if available.major > used.major:
                major_alerts.append(alert)
                continue
            if available.minor > used.minor:
                minor_alerts.append(alert)
                continue
            if available.patch > used.patch:
                patch_alerts.append(alert)
                continue
            assert (  # noqa  B011  TODO:  Do not call assert False since python -O removes these calls. Instead callers should raise AssertionError().
                False
            ), "unable to parse version differences."
        except Exception as e:
            parse_errors.append((line, e))

    if parse_errors:
        print("Parsing Errors:")
        for line, e in parse_errors:
            print(f"  {line}: {e}")
        print()
    if major_alerts:
        print("Major Updates Available:")
        print_alerts(major_alerts)
        print()
    if minor_alerts:
        print("Minor Updates Available:")
        print_alerts(minor_alerts)
        print()
    if patch_alerts:
        print("Patch Updates Available:")
        print_alerts(patch_alerts)

    exit_with_failure = (
        parse_errors
        or len(major_alerts) > MAJOR_TOLERANCE
        or len(minor_alerts) > MINOR_TOLERANCE
    )
    if exit_with_failure:
        exit(1)


if __name__ == "__main__":
    main()
