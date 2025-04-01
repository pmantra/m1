import traceback
import warnings
from typing import Set

from common import stats

METRIC_NAME = "mono_sqlalchemy_model_access"
_DEFAULT_REDUCED_SAMPLE_RATE = 0.1


def log_model_usage(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    model_name: str,
    *,
    pod_name: str,
    exclude_files: Set[str] = None,  # type: ignore[assignment] # Incompatible default for argument "exclude_files" (default has type "None", argument has type "Set[str]")
    deprecation_warning: str = None,  # type: ignore[assignment] # Incompatible default for argument "deprecation_warning" (default has type "None", argument has type "str")
):
    if deprecation_warning:
        warnings.warn(  # noqa  B028  TODO:  No explicit stacklevel keyword argument found. The warn method from the warnings module uses a stacklevel of 1 by default. This will only show a stack trace for the line on which the warn method is called. It is therefore recommended to use a stacklevel of 2 or greater to provide more information to the user.
            deprecation_warning, DeprecationWarning
        )

    if exclude_files is None:
        exclude_files = []  # type: ignore[assignment] # Incompatible types in assignment (expression has type "List[Never]", variable has type "Optional[Set[str]]")

    stack = traceback.extract_stack()
    referer_file = extract_referer(stack)
    if referer_file in exclude_files:
        return None

    stats.increment(
        metric_name=METRIC_NAME,
        pod_name=pod_name,  # type: ignore[arg-type] # Argument "pod_name" to "increment" has incompatible type "str"; expected "PodNames"
        tags=[
            f"model_name:{model_name}",
            f"referer_file:{referer_file}",
        ],
        # this metric is mostly to show the trend
        # sampling to reduce costs
        sample_rate=_DEFAULT_REDUCED_SAMPLE_RATE,
    )


def extract_referer(
    stack: traceback.StackSummary,
    *,
    orm_predicate: str = "sqlalchemy",
    caller_predicate: str = "/api/",
    default: str = "Unknown referer",
) -> str:
    """Extracts the file that loaded the SQLAlchemy Model from a stack trace"""
    # The files in our code base preceding the `orm_predicate` references are our target
    sqlalchemy_index = next(
        (i for (i, f) in enumerate(stack) if orm_predicate in f.filename), 0
    )
    # All of our code that we care about should contain the `caller_predicate` in the filepath.
    our_code_callers = [
        f for f in stack[:sqlalchemy_index] if caller_predicate in f.filename
    ]
    if not our_code_callers:
        return default

    return our_code_callers[-1].filename
