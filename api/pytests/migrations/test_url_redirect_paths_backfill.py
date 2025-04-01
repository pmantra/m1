from unittest.mock import patch

from utils.migrations.backfill_url_redirect_paths import create_url_redirect_paths


def test_existing_url_redirect_path(factories):
    """
    When a URLRedirectPath with a given path already exists,
    test that we do not create another one with the same path.
    """
    url_redirect_path = factories.URLRedirectPathFactory.create()

    with patch(
        "utils.migrations.backfill_url_redirect_paths.URL_REDIRECT_PATHS",
        [url_redirect_path.path],
    ):
        paths_to_create = create_url_redirect_paths()

        assert len(paths_to_create) == 0


def test_no_existing_url_redirect_path():
    """
    When no URLRedirectPath with a given path already exists,
    test that we create one with the path.
    """
    with patch(
        "utils.migrations.backfill_url_redirect_paths.URL_REDIRECT_PATHS",
        ["URL_REDIRECT_PATH"],
    ):
        paths_to_create = create_url_redirect_paths()

        assert len(paths_to_create) == 1
