import json
import sys
import time
from typing import Any, Literal


def err(msg: str) -> None:
    print(msg, file=sys.stderr)  # noqa


def log(level: Literal["INFO", "WARNING", "ERROR"], event: str, **kwargs: Any) -> None:
    kwargs["severity"] = level
    kwargs["msg"] = event
    kwargs["logger"] = "test_results"
    kwargs["timestamp"] = time.time_ns() // 1_000_000
    print(json.dumps(kwargs))  # noqa
