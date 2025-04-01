import enum
from unittest.mock import patch

import pytest
from httpproblem import Problem

from direct_payment.treatment_procedure.pytests.conftest import (  # noqa: F401
    fc_user as fc_user_fixture_import,
)
from direct_payment.treatment_procedure.pytests.conftest import (  # noqa: F401
    fertility_clinic,
)


class UserTypes(enum.Enum):
    default_user = "default_user"
    fc_user = "fc_user"
    unauthorized_user = "unauthorized_user"


def mock_get_article_by_slug_implementation(slug: str, category: str):
    if slug == "non-existent-article-slug":
        raise Problem(404, detail="Article not found.")
    else:
        return {"status_code": 200, "title": "mock article"}


@pytest.mark.parametrize(
    argnames="endpoint, user_type, expected_status",
    argvalues=[
        (
            "/api/v1/direct_payment/benefits_experience_help/articles",
            UserTypes.default_user,
            200,
        ),
        (
            "/api/v1/direct_payment/benefits_experience_help/articles/non-existent-article-slug",
            UserTypes.default_user,
            404,
        ),
        (
            "/api/v1/direct_payment/benefits_experience_help/articles/getting-started",
            UserTypes.default_user,
            200,
        ),
        (
            "/api/v1/direct_payment/benefits_experience_help/articles/getting-started",
            UserTypes.unauthorized_user,
            200,
        ),
        (
            "/api/v1/direct_payment/fertility_clinic_portal_help/articles",
            UserTypes.fc_user,
            200,
        ),
        (
            "/api/v1/direct_payment/fertility_clinic_portal_help/articles/non-existent-article-slug",
            UserTypes.fc_user,
            404,
        ),
        (
            "/api/v1/direct_payment/fertility_clinic_portal_help/articles/infertility-diagnosis",
            UserTypes.fc_user,
            200,
        ),
        (
            "/api/v1/direct_payment/fertility_clinic_portal_help/articles/infertility-diagnosis",
            UserTypes.unauthorized_user,
            401,
        ),
        (
            "/api/v1/direct_payment/general/articles/non-existent-article-slug",
            UserTypes.default_user,
            404,
        ),
        (
            "/api/v1/direct_payment/general/articles/terms-and-conditions",
            UserTypes.default_user,
            200,
        ),
        (
            "/api/v1/direct_payment/general/articles/terms-and-conditions",
            UserTypes.unauthorized_user,
            401,
        ),
    ],
)
@patch("direct_payment.help.services.contentful.MMBContentfulClient")
def test_endpoints(
    mock_contentful_client,
    client,
    endpoint,
    user_type,
    expected_status,
    api_helpers,
    factories,
    fc_user_fixture_import,  # noqa: F811
):
    mock_instance = mock_contentful_client.return_value
    mock_instance.get_article_by_slug.side_effect = (
        mock_get_article_by_slug_implementation
    )

    user = None
    if user_type == UserTypes.default_user:
        user = factories.DefaultUserFactory.create()
    elif user_type == UserTypes.fc_user:
        user = fc_user_fixture_import

    response = client.get(endpoint, headers=api_helpers.json_headers(user=user))
    assert response.status_code == expected_status
