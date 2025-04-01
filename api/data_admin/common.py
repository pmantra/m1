import os
import os.path

from utils.gcp import safe_get_project_id


def check_environment():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    """
    Check k8s config, gcp compute metadata and others
    """
    _pid = safe_get_project_id()
    project_allowed = (
        _pid == "local-development"
        or _pid.startswith("maven-clinic-qa")
        or _pid == "maven-clinic-sandbox"
        or _pid == "maven-clinic-staging"
        or _pid == "gitlab-saas"
    )
    return project_allowed and os.environ.get("DATA_ADMIN_ALLOWED") == "YES"


def types_to_dropdown_options(cls):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    """
    Convert type class attributes into dropdown list options.
    :return: iterable of dicts
    """
    return [a for a in vars(cls) if not a.startswith("__")]
