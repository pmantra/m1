import requests


class GitLabClient:
    def __init__(self, gitlab_token, gitlab_project_id, gitlab_url):  # type: ignore[no-untyped-def]
        self.token = gitlab_token
        self.project_id = gitlab_project_id
        self.gitlab_url = gitlab_url

        if not all([self.token, self.project_id]):
            raise ValueError(
                "Missing required GitLab configuration (GITLAB_TOKEN, GITLAB_PROJECT_ID)"
            )

    def post_mr_comment(self, mr_id, comment) -> bool:  # type: ignore[no-untyped-def]
        """Post a comment to a GitLab merge request"""
        if not mr_id:
            print("Missing merge request ID")  # noqa
            return False

        url = f"{self.gitlab_url}/api/v4/projects/{self.project_id}/merge_requests/{mr_id}/notes"
        headers = {"PRIVATE-TOKEN": self.token}
        data = {"body": comment}

        try:
            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            print(f"Error posting to GitLab: {e}")  # noqa
            return False


def format_validation_results(validation_results) -> str:  # type: ignore[no-untyped-def]
    """Format validation results into a readable markdown comment for GitLab"""

    markdown = "## Migration Review Results:\n\n"
    markdown += "This review comment is generated via a pre-release version of our own AI Reviewer. It is meant to be used as an aid for basic DB migration checks. For feedback, please reach out to the Core Services Team.\n\n"

    for result in validation_results:
        rule_name = result["rule"].replace(".txt", "")
        status_emoji = "✅" if result["validation_result"] == "success" else "❌"

        markdown += f"### {status_emoji} Rule: {rule_name}\n"
        markdown += f"{result['explanation']}\n\n"

    return markdown
