from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from direct_payment.pharmacy.tasks.esi_parser.esi_converter import (
    D2,
    D3,
    check_record_status,
    convert_to_health_plan_ytd_spend,
    year_converter,
)


def test_d2_converter():
    input = D2("foo")
    assert Decimal("200.00") == input.convert("20000")


def test_d3_converter():
    input = D3("bar")
    assert Decimal("20.000") == input.convert(20000)


def test_deductible_converter_positive():
    record = MagicMock()
    record.accumulator_balance_qualifier_1 = "04"
    record.accumulator_applied_amount_1 = "0000001045"
    record.action_code_1 = "+"
    record.accumulator_balance_qualifier_2 = "05"
    record.accumulator_applied_amount_2 = "0000001000"
    record.action_code_2 = "+"
    record.date_of_service = "20231011"
    ret = convert_to_health_plan_ytd_spend(record, "mock")
    assert ret.deductible_applied_amount == 1045
    assert ret.oop_applied_amount == 1000


def test_deductible_converter_negative():
    record = MagicMock()
    record.accumulator_balance_qualifier_1 = "04"
    record.accumulator_applied_amount_1 = "0000001045"
    record.action_code_1 = "-"
    record.accumulator_balance_qualifier_2 = "05"
    record.accumulator_applied_amount_2 = "0000001000"
    record.action_code_2 = "-"
    record.date_of_service = "20231011"
    ret = convert_to_health_plan_ytd_spend(record, "mock")
    assert ret.deductible_applied_amount == -1045
    assert ret.oop_applied_amount == -1000


def test_deductible_oop_converter_oop_only():
    record = MagicMock()
    record.accumulator_balance_qualifier_1 = "05"
    record.accumulator_applied_amount_1 = "0000001045"
    record.action_code_1 = "+"
    record.accumulator_balance_qualifier_2 = ""
    record.accumulator_applied_amount_2 = ""
    record.action_code_2 = ""
    record.date_of_service = "20231011"
    ret = convert_to_health_plan_ytd_spend(record, "mock")
    assert ret.deductible_applied_amount == 0
    assert ret.oop_applied_amount == 1045


def test_non_deductible_noop():
    record = MagicMock()
    record.accumulator_balance_qualifier_1 = "03"
    record.accumulator_applied_amount_1 = "0000002000"
    record.date_of_service = "20231011"
    with pytest.raises(ValueError):
        convert_to_health_plan_ytd_spend(record, "mock")


def test_reject_dr_record():
    record = MagicMock()
    record.transmission_file_type = "DR"
    record.transaction_response_status = "R"
    record.reject_code = "0F3"

    assert (True, "Accumulator Mismatch") == check_record_status(record)


def test_reject_dr_unknown_code():
    record = MagicMock()
    record.transmission_file_type = "DR"
    record.transaction_response_status = "R"
    record.reject_code = "089"
    assert (True, "089") == check_record_status(record)


def test_reject_dr_duplicate_record():
    record = MagicMock()
    record.transmission_file_type = "DR"
    record.transaction_response_status = "E"
    record.reject_code = "081"
    assert (True, "Duplicate Record") == check_record_status(record)


def test_normal_record():
    record = MagicMock()
    record.transmission_file_type = "DQ"
    record.transaction_response_status = ""
    record.reject_code = ""
    assert (False, None) == check_record_status(record)


def test_dr_approved_record():
    record = MagicMock()
    record.transmission_file_type = "DR"
    record.transaction_response_status = "A"
    record.reject_code = ""
    assert (True, None) == check_record_status(record)


def test_year_converter():
    assert 2023 == year_converter("20231011")
