from __future__ import annotations

from auth0 import authentication


class TokenClient:
    __slots__ = ("domain", "audience", "client_id", "client_secret", "oauth_token")

    def __init__(
        self,
        *,
        domain: str | None = None,
        audience: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
    ):
        self.domain = domain
        self.audience = audience
        self.client_id = client_id
        self.client_secret = client_secret
        self.oauth_token = self._oauth_token()

    def _oauth_token(self) -> authentication.GetToken:
        return authentication.GetToken(
            domain=self.domain,
            client_id=self.client_id,
            client_secret=self.client_secret,
        )

    def management_token(self) -> str:
        api_url = f"https://{self.domain}/api/v2/"
        response = self.oauth_token.client_credentials(api_url)
        return response["access_token"]

    def authorization_code(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self,
        *,
        code: str,
        redirect_uri: str | None,
    ):
        return self.oauth_token.authorization_code(code=code, redirect_uri=redirect_uri)

    def login(
        self,
        *,
        username: str,
        password: str,
        realm: str,
        scope: str,
        forwarded_for: str = None,  # type: ignore[assignment] # Incompatible default for argument "forwarded_for" (default has type "None", argument has type "str")
    ) -> tuple[str, str]:
        return self.oauth_token.login(
            username=username,
            password=password,
            realm=realm,
            scope=scope,
            audience=self.audience,
            forwarded_for=forwarded_for,
        )

    def refresh_token(
        self,
        *,
        refresh_token: str,
    ) -> tuple[str, str]:
        return self.oauth_token.refresh_token(refresh_token=refresh_token)

    def revoke_token(self, *, refresh_token):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        revoker = authentication.RevokeToken(
            domain=self.domain,
            client_id=self.client_id,
            client_secret=self.client_secret,
        )
        revoker.revoke_refresh_token(token=refresh_token)
