from airflow.utils import with_app_context
from authn.domain import service
from authn.util.database_compare_tool import AuthnDataComparer
from common.authn_api.internal_client import AuthnApiInternalClient
from common.constants import current_web_origin


@with_app_context(team_ns="core_services", service_ns="authentication")
def database_compare_job() -> None:
    sso_service = service.SSOService()
    authn_service = service.AuthenticationService()
    user_service = service.UserService()
    authnapi_client = AuthnApiInternalClient(
        base_url=f"{current_web_origin()}/api/v1/-/oauth/"
    )
    worker = AuthnDataComparer(
        sso_service=sso_service,
        authn_service=authn_service,
        user_service=user_service,
        authnapi_client=authnapi_client,
    )

    worker.check_user_external_identity()
    worker.check_user()
    worker.check_user_auth()
    worker.check_identity_provider()
    worker.check_org_auth()
