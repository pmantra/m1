from types import MappingProxyType

from authn.resources import auth, mfa, migration, sso, user


def add_routes(api):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    for url_path, resource in _URLS.items():
        api.add_resource(resource, url_path)
    return api


_URLS = MappingProxyType(
    {
        "/v1/_/password_strength_score": user.PasswordStrengthScoreResource,
        "/v1/api_key": user.ApiKeyResource,
        "/v1/mfa/enroll": mfa.MFAEnrollmentResource,
        "/v1/mfa/force_enroll": mfa.MFAForceEnrollmentResource,
        "/v1/mfa/remove": mfa.MFACancellationResource,
        "/v1/mfa/verify": mfa.MFAVerificationResource,
        "/v1/mfa/resend_code": mfa.MFAResendCodeResource,
        "/v1/mfa/enforcement": mfa.MFAEnforcementResource,
        "/v1/mfa/company_mfa_sync": mfa.MFACompanyDataResource,
        "/v1/users": user.UsersResource,
        "/v1/users/<email>/email_confirm": user.ConfirmEmailResource,
        "/v1/users/<email>/password_reset": user.PasswordResetResource,
        "/v1/users/<int:user_id>": user.UserResource,
        "/v1/users/<int:user_id>/setup": sso.UserSetupResource,
        "/v1/users/sso_user_creation": sso.SsoUserCreationResource,
        "/v1/users/start_delete_request/<int:user_id>": user.GDPRResource,
        "/v1/users/restore/<int:user_id>": user.UserRestore,
        "/v1/users/verification_email": user.UserVerificationEmailResource,
        "/v1/users/sso_relink": user.SsoUserRelinkResource,
        "/v1/oauth/token": auth.OauthTokenResource,
        "/v1/oauth/token/refresh": auth.OauthRefreshTokenResource,
        "/v1/oauth/token/validate": auth.OauthValidateTokenResource,
        "/v1/oauth/token/revoke": auth.OauthRevokeTokenResource,
        "/v1/oauth/authorize": auth.AuthorizationResource,
        "/v1/oauth/logout": auth.LogoutResource,
        "/v1/oauth/signup": auth.SignupResource,
        "/v1/-/users/post_signup_steps": user.PostUserCreationResource,
        "/v1/-/users/get_identities/<int:user_id>": user.GetIdentitiesResource,
        "/v1/-/users/get_org_id/<int:user_id>": user.GetOrgIdResource,
        "/v1/-/users/sync_user_data": user.SyncUserDataResource,
        "/v1/-/authn_migration/retrieve_authn_data/<name>": migration.RetrievalAuthnDataResource,
        "/v1/-/authn_migration/upsert_authn_data": migration.UpsertAuthnDataResource,
    }
)
