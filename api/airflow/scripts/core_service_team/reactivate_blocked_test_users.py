from airflow.utils import with_app_context
from authn.jobs.activate_blocked_qa_test_accounts import activate_blocked_test_accounts


@with_app_context(team_ns="core_services", service_ns="authentication")
def activate_blocked_test_user_job() -> None:
    activate_blocked_test_accounts(max_page=4, dry_run=False)
