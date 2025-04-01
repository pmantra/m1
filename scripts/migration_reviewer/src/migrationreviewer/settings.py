import environ


@environ.config(prefix=None, frozen=True)
class MigrationReviewerSettings:
    """Core settings for the migration reviewer config.
    See Also:
    - `environ-config`_

    """

    gemini_api_key: str = environ.var(name="GEMINI_API_KEY_QA1")
    gitlab_token: str = environ.var(name="GITLAB_TOKEN")
    gitlab_project_id: str = environ.var(name="CI_PROJECT_ID")
    gitlab_url: str = environ.var(name="GITLAB_URL", default="https://gitlab.com")
