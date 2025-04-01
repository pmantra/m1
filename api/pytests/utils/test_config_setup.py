import os
from unittest import mock

from sqlalchemy.engine import url

from utils.config_setup import apply_dsn_namespacing, create_sqlalchemy_binds


class TestConfigureSqlAlchemyBinds:

    # db envs = environment variables for maven / audit DB urls
    # ns envs = namespace environment variable for multi-tenant QA clusters
    #
    # In multi-tenant QA clusters, you have the 1) pristine instance and 2) each dev has their own sharded namespaced instance
    # These tests ensure this app is configurable for either based on the ENVs passed in.
    #
    #                   With db envs                          | without db envs
    #                 ____________________________________________________________________________
    # with ns env     | test_with_db_with_namespace_envs      |  test_without_db_with_namespace_envs
    #                 | > this is a dev's own QA instance     |  > this should never happen
    #                 |                                       |
    # without ns env  | test_with_db_without_namespace_envs   |  test_without_any_envs
    #                 | > this is prod or pristine QA         |  > this is a local-dev
    #
    #

    _mock_namespace = "cool-namespace-my+fell0w_human"
    _mock_default_url = "mysql+pymysql://hello:world@planet:1/pups?are=awesome"
    _mock_replica1_url = "mysql+pymysql://hello:world@planet:1/birds?are=fun"

    # Clear the environ object for a clean slate first
    @mock.patch.dict(os.environ, {}, clear=True)
    @mock.patch.dict(os.environ, {"DEFAULT_DB_URL": _mock_default_url})
    @mock.patch.dict(os.environ, {"REPLICA1_DB_URL": _mock_replica1_url})
    @mock.patch.dict(os.environ, {"APP_ENVIRONMENT_NAMESPACE": _mock_namespace})
    def test_with_db_with_namespace_envs(self):
        # Given
        # When
        result = create_sqlalchemy_binds()
        # Then

        # Convert the sqlalchemy.engine.url.URL object to a string first
        assert (
            str(result["default"])
            == f"mysql+pymysql://hello:world@planet:1/{self._mock_namespace}__pups?are=awesome"
        )
        assert result["default"].database == f"{self._mock_namespace}__pups"
        assert (
            str(result["replica1"])
            == f"mysql+pymysql://hello:world@planet:1/{self._mock_namespace}__birds?are=fun"
        )
        assert result["replica1"].database == f"{self._mock_namespace}__birds"

    @mock.patch.dict(os.environ, {}, clear=True)
    @mock.patch.dict(os.environ, {"APP_ENVIRONMENT_NAMESPACE": _mock_namespace})
    def test_without_db_with_namespace_envs(self):
        # Given
        # When
        result = create_sqlalchemy_binds()
        # Then

        assert (
            str(result["default"])
            == f"mysql+pymysql://root:root@mysql/{self._mock_namespace}__maven?charset=utf8mb4"
        )
        assert result["default"].database == f"{self._mock_namespace}__maven"
        assert (
            str(result["replica1"])
            == f"mysql+pymysql://root:root@mysql/{self._mock_namespace}__maven?charset=utf8mb4"
        )
        assert result["replica1"].database == f"{self._mock_namespace}__maven"

    @mock.patch.dict(os.environ, {}, clear=True)
    @mock.patch.dict(os.environ, {"DEFAULT_DB_URL": _mock_default_url})
    @mock.patch.dict(os.environ, {"REPLICA1_DB_URL": _mock_replica1_url})
    def test_with_db_without_namespace_envs(self):
        # Given
        # When
        result = create_sqlalchemy_binds()
        # Then

        assert str(result["default"]) == self._mock_default_url
        assert result["default"].database == "pups"
        assert str(result["replica1"]) == self._mock_replica1_url
        assert result["replica1"].database == "birds"

    @mock.patch.dict(os.environ, {}, clear=True)
    def test_without_any_envs(self):
        # Given
        # When
        result = create_sqlalchemy_binds()
        # Then

        assert (
            str(result["default"])
            == "mysql+pymysql://root:root@mysql/maven?charset=utf8mb4"
        )
        assert result["default"].database == "maven"
        assert (
            str(result["replica1"])
            == "mysql+pymysql://root:root@mysql/maven?charset=utf8mb4"
        )
        assert result["replica1"].database == "maven"


class TestApplyDsnNamespacing:
    _mock_namespace = "my-namespace"

    @mock.patch.dict(os.environ, {"APP_ENVIRONMENT_NAMESPACE": _mock_namespace})
    def test_with_value(self):
        # Given
        dsn = url.make_url("mysql+pymysql://root:root@mysql/maven?charset=utf8mb4")
        # When
        namespaced = apply_dsn_namespacing(dsn)
        # Then
        assert namespaced.database == f"{self._mock_namespace}__maven"

    @mock.patch.dict(os.environ, {"APP_ENVIRONMENT_NAMESPACE": _mock_namespace})
    def test_without_value(self):
        # Given
        dsn = None
        # When
        namespaced = apply_dsn_namespacing(dsn)
        # Then
        assert namespaced is None

    @mock.patch.dict(os.environ, {}, clear=True)
    def test_without_namespace_veriable(self):
        # Given
        dsn = url.make_url("mysql+pymysql://root:root@mysql/maven?charset=utf8mb4")
        # When
        namespaced = apply_dsn_namespacing(dsn)
        # Then
        assert namespaced == dsn
