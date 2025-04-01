from airflow.utils import with_app_context
from common.authn_api.internal_client import AuthnApiInternalClient
from common.constants import current_web_origin


@with_app_context(team_ns="core_services", service_ns="authentication")
def database_sync_job() -> None:
    authnapi_client = AuthnApiInternalClient(base_url=f"{current_web_origin()}/api")
    authnapi_client.trigger_data_sync(table_name="identity_provider", dryrun=True)
