"""
Metric util for decoupling foreign key with appointment table

The specific metric will be:
1. When property attr being accessed (both read and write)
2. When operations rely on foreign key happens, e.g. JOIN
"""

from common import stats

# ======= Metric Related Constants ===============
PROPERTY_ACCESS = "property_access.count"
PROPERTY_READ = "property_read"
PROPERTY_WRITE = "property_write"
# ================================================


def increment_metric(read: bool, model_name: str, failure: str = None):  # type: ignore[no-untyped-def,assignment] # Function is missing a return type annotation #type: ignore[assignment] # Incompatible default for argument "failure" (default has type "None", argument has type "str")
    """

    Args:
        read: Whether it's being called in read path or write path
        model_name: ORM model name, e.g. AppointmentMetaData
        failure: Failures in the call

    Returns:

    """
    tags = [
        f"orm_model: {model_name}",
        f"method:{PROPERTY_READ if read else PROPERTY_WRITE}",
    ]
    if failure:
        tags.append(f"failure: {failure}")
    stats.increment(
        metric_name=PROPERTY_ACCESS,
        tags=tags,
        pod_name=stats.PodNames.CARE_DISCOVERY,
    )
