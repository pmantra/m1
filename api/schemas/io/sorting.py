from functools import wraps
from operator import itemgetter


def sorted_by(*keys):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    def sort_results(fn):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        @wraps(fn)
        def wrapper(*args, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
            data = fn(*args, **kwargs)
            return sorted(data, key=itemgetter(*keys))

        return wrapper

    return sort_results
