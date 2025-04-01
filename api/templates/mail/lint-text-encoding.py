#!/usr/bin/env python3
from glob import glob
from sys import exit


def main() -> None:
    errors = []
    for path in glob("./*_text.j2"):
        try:
            with open(path, encoding="ascii", errors="strict") as f:
                f.readlines()
        except UnicodeDecodeError as e:
            errors.append(
                dict(path=path, start=e.args[2], end=e.args[3], msg=e.args[1])
            )

    exit_code = 0
    for e in errors:
        exit_code = 1
        print("{path}:{start}-{end} \n{msg}\n".format(**e))
    exit(exit_code)


if __name__ == "__main__":
    main()
