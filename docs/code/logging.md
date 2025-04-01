# Logging

Python applications are expected to emit line delimited json objects on stdout for their logs. These logs can be consumed directly using `kubectl log` (and jq), or be queried interactively through the [GCP Console Logs Viewer](https://console.cloud.google.com/logs/viewer).


### What makes a good log?

- The event text should be a constant string so that we can find all instances of a log regardless of the context. Ideally, event texts are a short english sentence.

        This fixed string can be searched for verbatim.

- The context for the log should be communicated using structured metadata. Primary keys should be used to identify database entities so that all logs pertaining to a particular identifier can be queried easily.


        {"event": "User uploaded profile image.", "user_id": 123, "image_content_length": 4096}

- Logs should contain the minimum amount of information required to reconstruct an understanding of what happened in the application. Our log store is **never an appropriate place for PII or PHI**.


### How do I pick a log level?

level | should express...
---|---
`debug` | intermediate state following the happy path
`info` | entry points such as beginning a request, task, or script...<br>or an important branch decision that may influence what happens in the future
`warning` | recoverable sad paths such as access denials and state conflicts
`error` | irrecoverable programming errors or upstream service errors such as database or api outage

## Example

```py
from utils.log import logger
log = logger(__name__)  # __name__ will be included in log metadata as "logger".


def sum_of(*values):
    n_values = len(values)
    log.info("Calculating sum of values.", n_values=n_values)

    if n_values == 0:
        log.warning("At least one value is required to compute a sum.")
        return None

    s = 0
    for n in values:
        s += n
    return s


assert sum_of(1, 2, 3) == 6
# { "event": "Calculating sum of values.", "n_values": 3, "logger": "__main__", "level": "info" }

assert sum_of() is None
# { "event": "Calculating sum of values.", "n_values": 0, "logger": "__main__", "level": "info" }
# { "event": "At least one value is required to compute a sum.", "logger": "__main__", "level": "warning" }
```

## Implemented By

- [`/api/utils/log.py`](/api/utils/log.py)

## Depends On

- [`structlog`](https://www.structlog.org/en/stable/)

