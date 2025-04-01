import copy
from datetime import datetime, timedelta
from time import sleep

import pytest

from models.failed_external_api_call import Status
from utils.failed_external_api_call_recorder import FailedVendorAPICallRecorder
from utils.random_string import generate_random_string


@pytest.fixture
def failed_vendor_api_call_recorder():
    return FailedVendorAPICallRecorder()


class TestFailedVendorAPICallRecorder:
    def test_create_record_and_load_by_id(self, failed_vendor_api_call_recorder):
        external_id = generate_random_string(20)
        called_by = generate_random_string(10)
        vendor_name = generate_random_string(10)
        api_name = generate_random_string(10)
        create_result = failed_vendor_api_call_recorder.create_record(
            external_id,
            {"a": "foo", "b": "lol"},
            called_by,
            vendor_name,
            api_name,
            Status.pending,
        )
        assert create_result is not None

        load_by_external_id_result = (
            failed_vendor_api_call_recorder.get_record_by_external_id(external_id)
        )
        assert load_by_external_id_result is not None
        assert load_by_external_id_result.id > 0
        assert load_by_external_id_result.payload == {"a": "foo", "b": "lol"}
        assert load_by_external_id_result.external_id == external_id
        assert load_by_external_id_result.called_by == called_by
        assert load_by_external_id_result.vendor_name == vendor_name
        assert load_by_external_id_result.api_name == api_name
        assert load_by_external_id_result.status == Status.pending

        load_by_id_result = failed_vendor_api_call_recorder.get_record_by_id(
            load_by_external_id_result.id
        )
        assert load_by_id_result is not None
        assert load_by_id_result.id == load_by_external_id_result.id
        assert load_by_id_result.payload == {"a": "foo", "b": "lol"}
        assert load_by_id_result.external_id == external_id
        assert load_by_id_result.called_by == called_by
        assert load_by_id_result.vendor_name == vendor_name
        assert load_by_id_result.api_name == api_name
        assert load_by_id_result.status == Status.pending

        load_by_non_existing_external_id_result = (
            failed_vendor_api_call_recorder.get_record_by_external_id(
                generate_random_string(12)
            )
        )
        assert load_by_non_existing_external_id_result is None

    def test_update_status(self, failed_vendor_api_call_recorder):
        external_id = generate_random_string(20)
        called_by = generate_random_string(10)
        vendor_name = generate_random_string(10)
        api_name = generate_random_string(10)
        failed_vendor_api_call_recorder.create_record(
            external_id,
            {"a": "foo", "b": "lol"},
            called_by,
            vendor_name,
            api_name,
            Status.pending,
        )

        original_data = copy.deepcopy(
            failed_vendor_api_call_recorder.get_record_by_external_id(external_id)
        )
        assert original_data is not None

        sleep(1)

        updated_result = failed_vendor_api_call_recorder.set_status(
            original_data.id, Status.processed
        )
        assert updated_result

        updated_data = failed_vendor_api_call_recorder.get_record_by_external_id(
            external_id
        )
        assert updated_data.status == Status.processed
        assert updated_data.modified_at > original_data.modified_at

    def test_load_by_time_and_status(self, failed_vendor_api_call_recorder):
        start = datetime.utcnow()
        external_id_one = generate_random_string(20)
        called_by_one = generate_random_string(10)
        vendor_name_one = generate_random_string(10)
        api_name_one = generate_random_string(10)
        failed_vendor_api_call_recorder.create_record(
            external_id_one,
            {"a": "foo1", "b": "lol1"},
            called_by_one,
            vendor_name_one,
            api_name_one,
            Status.pending,
        )

        sleep(1)
        external_id_two = generate_random_string(20)
        called_by_two = generate_random_string(10)
        vendor_name_two = generate_random_string(10)
        api_name_two = generate_random_string(10)
        failed_vendor_api_call_recorder.create_record(
            external_id_two,
            {"a": "foo2", "b": "lol2"},
            called_by_two,
            vendor_name_two,
            api_name_two,
            Status.processed,
        )

        sleep(1)
        external_id_three = generate_random_string(20)
        called_by_three = generate_random_string(10)
        vendor_name_three = generate_random_string(10)
        api_name_three = generate_random_string(10)
        failed_vendor_api_call_recorder.create_record(
            external_id_three,
            {"a": "foo3", "b": "lol3"},
            called_by_three,
            vendor_name_three,
            api_name_three,
            Status.pending,
        )

        end = datetime.utcnow()

        result_one = failed_vendor_api_call_recorder.get_record_by_status(
            start_time=start - timedelta(seconds=1),
            end_time=end + timedelta(seconds=2),
            status=Status.pending,
        )
        assert len(result_one) == 2

        result_two = failed_vendor_api_call_recorder.get_record_by_status(
            start_time=start - timedelta(seconds=1),
            end_time=end + timedelta(seconds=2),
            status=Status.processed,
        )
        assert len(result_two) == 1

        result_three = failed_vendor_api_call_recorder.get_record_by_status(
            start_time=start - timedelta(seconds=1),
            end_time=end + timedelta(seconds=2),
            status=Status.failed,
        )
        assert len(result_three) == 0

        result_four = failed_vendor_api_call_recorder.get_record_by_status(
            start_time=start - timedelta(seconds=2),
            end_time=start - timedelta(seconds=1),
            status=Status.pending,
        )
        assert len(result_four) == 0

        result_five = failed_vendor_api_call_recorder.get_record_by_status(
            start_time=end + timedelta(seconds=1),
            end_time=end + timedelta(seconds=2),
            status=Status.pending,
        )
        assert len(result_five) == 0
