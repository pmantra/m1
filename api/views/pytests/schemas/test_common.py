from unittest import mock

import pymysql
import pytest
import sqlalchemy
from marshmallow_v1 import fields

from views.schemas.common import MavenSchema


class SampleSchema(MavenSchema):
    name = fields.Method("get_name")

    def get_name(self, obj):
        return obj["name"]


class TestException(Exception):
    pass


class TestMavenSchema:
    @mock.patch(
        "views.schemas.common.should_attempt_dump_retry",
        return_value=False,
    )
    def test_dump_normal_operation_success(
        self,
        mock_should_attempt_dump_retry,
    ):
        schema = SampleSchema()

        result = schema.dump({"name": "foo"}).data
        assert result["name"] == "foo"

        mock_should_attempt_dump_retry.assert_not_called()

    @mock.patch(
        "views.schemas.common.should_attempt_dump_retry",
        return_value=False,
    )
    @mock.patch(
        "views.schemas.common.Schema.dump",
        side_effect=pymysql.err.InternalError("oof"),
    )
    def test_dump_normal_operation_exception(
        self,
        mock_super_dump,
        mock_should_attempt_dump_retry,
    ):
        schema = SampleSchema()

        with pytest.raises(pymysql.err.InternalError):
            result = schema.dump({"name": "foo"}).data
            assert result["name"] == "foo"

        assert mock_super_dump.call_count == 1
        mock_should_attempt_dump_retry.assert_called_once()

    @mock.patch(
        "views.schemas.common.Schema.dump",
        side_effect=[
            TestException("test_exception"),
            None,  # dont except on the 2nd try
        ],
    )
    @mock.patch(
        "views.schemas.common.should_attempt_dump_retry",
        return_value=True,
    )
    def test_dump_flagged_operation_unmatched_exception(
        self,
        mock_should_attempt_dump_retry,
        mock_super_dump,
    ):
        schema = SampleSchema()

        with pytest.raises(TestException):
            result = schema.dump({"name": "foo"}).data
            assert result["name"] == "foo"

        assert mock_super_dump.call_count == 1
        mock_should_attempt_dump_retry.assert_not_called()

    @pytest.mark.parametrize(
        "serialize_exception",
        [
            pymysql.err.InternalError("oof"),
            pymysql.err.OperationalError("big oof"),
            sqlalchemy.exc.OperationalError("bigger oof", params=None, orig=None),
        ],
    )
    @mock.patch("views.schemas.common.Schema.dump")
    @mock.patch("views.schemas.common.should_attempt_dump_retry")
    def test_dump_flagged_operation_matched_exception(
        self,
        mock_should_attempt_dump_retry,
        mock_super_dump,
        serialize_exception,
    ):
        mock_should_attempt_dump_retry.return_value = True

        super_dump_result = mock.MagicMock()
        super_dump_result.data = {"name": "foo"}
        mock_super_dump.side_effect = [
            serialize_exception,
            super_dump_result,
        ]

        schema = SampleSchema()

        result = schema.dump({"name": "foo"}).data
        assert result["name"] == "foo"

        assert mock_super_dump.call_count == 2
        mock_should_attempt_dump_retry.assert_called_once()
