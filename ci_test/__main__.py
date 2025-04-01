import enum
import sys

from ci_test.log import err


class Command(enum.Enum):
    GENERATE = "generate"
    TEST = "test"
    REPORT = "report"


if __name__ == "__main__":
    try:
        command = Command(sys.argv[1])
    except (IndexError, ValueError):
        err(f"Usage: python -m ci_test {'|'.join(c.value for c in Command)}")
        sys.exit(1)
    if command == Command.GENERATE:
        from ci_test.generate import main
    elif command == Command.TEST:
        from ci_test.test import main
    elif command == Command.REPORT:
        from ci_test.report import main
    else:
        raise NotImplementedError(f"'{command}' has not yet been implemented.")
    main()
