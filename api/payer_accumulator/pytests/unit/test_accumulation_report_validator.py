import datetime
from typing import List, Union

import pytest
from structlog import testing

from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedure,
)
from direct_payment.treatment_procedure.pytests.factories import (
    TreatmentProcedureFactory,
)
from payer_accumulator.accumulation_report_validator import AccumulationReportValidator
from payer_accumulator.common import TreatmentAccumulationStatus
from payer_accumulator.pytests.conftest import TP_UUID_2, TP_UUID_4, TP_UUID_5
from payer_accumulator.pytests.factories import (
    AccumulationTreatmentMappingFactory,
    PayerAccumulationReportsFactory,
)
from wallet.models.constants import WalletState
from wallet.models.reimbursement import ReimbursementRequest
from wallet.pytests.factories import (
    MemberHealthPlanFactory,
    ReimbursementRequestCategoryFactory,
    ReimbursementRequestFactory,
    ReimbursementWalletFactory,
)


def make_accumulation_mappings(
    all_data: List[Union[TreatmentProcedure, ReimbursementRequest]], report_id: int
):
    return [
        AccumulationTreatmentMappingFactory.create(
            treatment_procedure_uuid=data.uuid,
            reimbursement_request_id=None,
            treatment_accumulation_status=TreatmentAccumulationStatus.PROCESSED,
            deductible=100,
            oop_applied=100,
            report_id=report_id,
        )
        if isinstance(data, TreatmentProcedure)
        else AccumulationTreatmentMappingFactory.create(
            treatment_procedure_uuid=None,
            reimbursement_request_id=data.id,
            treatment_accumulation_status=TreatmentAccumulationStatus.PROCESSED,
            deductible=100,
            oop_applied=100,
            report_id=report_id,
        )
        for data in all_data
    ]


@pytest.fixture(scope="function")
def validate_accumulation_mappings(
    validate_procedures_and_requests, validate_procedures_and_requests_2
):
    data = validate_procedures_and_requests + validate_procedures_and_requests_2
    return make_accumulation_mappings(data, 2)


@pytest.fixture(scope="function")
def validate_081_mappings(validate_procedures_and_requests_2):
    make_accumulation_mappings(validate_procedures_and_requests_2, 2)


@pytest.fixture
def validate_category():
    return ReimbursementRequestCategoryFactory.create(label="fertility")


@pytest.fixture(scope="function")
def validate_procedures_and_requests(validate_wallet, validate_category):
    return [
        TreatmentProcedureFactory.create(
            uuid=TP_UUID_2,
            reimbursement_wallet_id=validate_wallet.id,
            member_id=123,
        ),
        ReimbursementRequestFactory.create(
            id=1022876944139882075,
            reimbursement_wallet_id=validate_wallet.id,
            reimbursement_request_category_id=validate_category.id,
            service_start_date=datetime.datetime(year=2025, month=5, day=2),
        ),
        ReimbursementRequestFactory.create(
            id=1022876944139882076,
            reimbursement_wallet_id=validate_wallet.id,
            reimbursement_request_category_id=validate_category.id,
            service_start_date=datetime.datetime(year=2025, month=5, day=3),
        ),
    ]


@pytest.fixture(scope="function")
def validate_procedures_and_requests_2(
    validate_wallet, validate_wallet_2, validate_category
):
    return [
        ReimbursementRequestFactory.create(
            id=802645817121709721,
            reimbursement_wallet_id=validate_wallet_2.id,
            reimbursement_request_category_id=validate_category.id,
            service_start_date=datetime.datetime(year=2025, month=5, day=1),
        ),
        TreatmentProcedureFactory.create(
            uuid=TP_UUID_5,
            reimbursement_wallet_id=validate_wallet_2.id,
            member_id=12,
        ),
    ]


@pytest.fixture(scope="function")
def validate_wallet():
    wallet = ReimbursementWalletFactory.create(id=10824, state=WalletState.QUALIFIED)
    return wallet


@pytest.fixture(scope="function")
def validate_wallet_2():
    wallet = ReimbursementWalletFactory.create(id=10823, state=WalletState.QUALIFIED)
    return wallet


@pytest.fixture(scope="function")
def validate_member_health_plans(
    employer_health_plan, employer_health_plan2, validate_wallet, validate_wallet_2
):
    return [
        MemberHealthPlanFactory.create(
            reimbursement_wallet_id=validate_wallet_2.id,
            reimbursement_wallet=validate_wallet_2,
            employer_health_plan=employer_health_plan,
            employer_health_plan_id=employer_health_plan.id,
            subscriber_insurance_id="U1234567801",
            patient_date_of_birth=datetime.date(2000, 1, 1),
            member_id=12,
            plan_start_at=datetime.datetime(year=2025, month=1, day=1),
        ),
        MemberHealthPlanFactory.create(
            reimbursement_wallet_id=validate_wallet.id,
            reimbursement_wallet=validate_wallet,
            employer_health_plan=employer_health_plan2,
            employer_health_plan_id=employer_health_plan2.id,
            subscriber_insurance_id="U1234567802",
            patient_date_of_birth=datetime.date(2000, 1, 1),
            member_id=123,
            plan_start_at=datetime.datetime(year=2025, month=1, day=1),
        ),
        MemberHealthPlanFactory.create(
            reimbursement_wallet_id=validate_wallet.id,
            reimbursement_wallet=validate_wallet,
            employer_health_plan=employer_health_plan2,
            employer_health_plan_id=employer_health_plan2.id,
            subscriber_insurance_id="U1234567802",
            patient_date_of_birth=datetime.date(2000, 1, 1),
            member_id=1234,
            plan_start_at=datetime.datetime(year=2025, month=1, day=1),
        ),
    ]


@pytest.fixture(scope="function")
def search_member_health_plans(
    employer_health_plan, employer_health_plan2, validate_wallet, validate_wallet_2
):
    return [
        MemberHealthPlanFactory.create(
            reimbursement_wallet_id=validate_wallet_2.id,
            reimbursement_wallet=validate_wallet_2,
            employer_health_plan=employer_health_plan,
            employer_health_plan_id=employer_health_plan.id,
            subscriber_insurance_id="U123456780231",
            patient_date_of_birth=datetime.date(2000, 1, 1),
            member_id=12,
        ),
        MemberHealthPlanFactory.create(
            reimbursement_wallet_id=validate_wallet.id,
            reimbursement_wallet=validate_wallet,
            employer_health_plan=employer_health_plan2,
            employer_health_plan_id=2,
            subscriber_insurance_id="U1234567802",
            patient_date_of_birth=datetime.date(2000, 1, 1),
            member_id=123,
        ),
        MemberHealthPlanFactory.create(
            reimbursement_wallet_id=validate_wallet.id,
            reimbursement_wallet=validate_wallet,
            employer_health_plan=employer_health_plan2,
            employer_health_plan_id=2,
            subscriber_insurance_id="U1234567802",
            patient_date_of_birth=datetime.date(2000, 1, 2),
            member_id=1234,
        ),
        MemberHealthPlanFactory.create(
            reimbursement_wallet_id=10825,
            reimbursement_wallet=ReimbursementWalletFactory.create(
                id=10825, state=WalletState.QUALIFIED
            ),
            employer_health_plan=employer_health_plan2,
            employer_health_plan_id=2,
            subscriber_insurance_id="U12345678042",
            patient_date_of_birth=datetime.date(2000, 1, 1),
            member_id=12345,
        ),
    ]


@pytest.fixture(scope="function")
def validate_member_health_plans_substring(
    validate_wallet, validate_wallet_2, employer_health_plan
):
    MemberHealthPlanFactory.create(
        reimbursement_wallet_id=validate_wallet_2.id,
        reimbursement_wallet=validate_wallet_2,
        employer_health_plan=employer_health_plan,
        employer_health_plan_id=employer_health_plan.id,
        subscriber_insurance_id="U12345678011111",
        patient_date_of_birth=datetime.date(2000, 1, 1),
        member_id=12,
    )
    MemberHealthPlanFactory.create(
        reimbursement_wallet_id=validate_wallet.id,
        reimbursement_wallet=validate_wallet,
        employer_health_plan=employer_health_plan,
        employer_health_plan_id=employer_health_plan.id,
        subscriber_insurance_id="U12345678022222",
        patient_date_of_birth=datetime.date(2000, 1, 1),
        member_id=123,
    )
    MemberHealthPlanFactory.create(
        reimbursement_wallet_id=validate_wallet.id,
        reimbursement_wallet=validate_wallet,
        employer_health_plan=employer_health_plan,
        employer_health_plan_id=employer_health_plan.id,
        subscriber_insurance_id="U12345678022221",
        patient_date_of_birth=datetime.date(2000, 1, 2),
        member_id=12345,
    )


@pytest.fixture(scope="function")
def validate_payer_report(uhc_payer):
    return PayerAccumulationReportsFactory.create(id=2, payer_id=uhc_payer.id)


@pytest.fixture
def report_equal_length_invalid():
    return """0MAVEN     Maven               160 Varick St 6th FlNew York          NY10013    2124571790UHG       2023102413:20:09T001                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                
423297100100202310241320092123456  1                              00202310242023021520230315U1234567801         99                    alice                                             paul                               2200001011                                                                                                                                                                                I0000000{0000000{0000000{0000010{000000000{000000000{0000000{000000000{000000000{20230215                                                                                                          
423297100100202310241320092123456  1                              00202310242023021520230315U1234567801         99                    alice                                             paul                               2200001011                                                                                                                                                                                I0000000{0000000{0000000{0001000{000000000{000000000{0001000{000000000{000000000{20230215                                                                                                          
423297100100202310241320092123456  1                              00202310242023021520230315U1234567802         99                    alice                                             paul                               2200001011                                                                                                                                                                                I0000000{0000000{0000000{0000030{000000000{000000000{0000000{000000000{000000000{20230215                                                                                                          
423297100100202310241320092123456  1                              00202310242023021520230315U1234567802         99                    alice                                             paul                               2200001011                                                                                                                                                                                I0000000{0000000{0000000{0000000{000000000{000000000{0000030{000000000{000000000{20230215                                                                                                          
8MAVEN     00000000010000000003    """


@pytest.fixture
def report_equal_length_valid():
    return """0MAVEN     Maven               160 Varick St 6th FlNew York          NY10013    2124571790UHG       2023102413:20:09T001                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                
423297100100202310241320092123456  1                              00202310242023021520230315U1234567801         99                    alice                                             paul                               2200001011                                                                                                                                                                                I0000000{0000000{0000000{0000020{000000000{000000000{0000000{000000000{000000000{20230215                                                                                                          
423297100100202310241320092123456  1                              00202310242023021520230315U1234567801         99                    alice                                             paul                               2200001011                                                                                                                                                                                I0000000{0000000{0000000{0000000{000000000{000000000{0000020{000000000{000000000{20230215                                                                                                          
423297100100202310241320092123456  1                              00202310242023021520230315U1234567802         99                    alice                                             paul                               2200001011                                                                                                                                                                                I0000000{0000000{0000000{0000030{000000000{000000000{0000000{000000000{000000000{20230215                                                                                                          
423297100100202310241320092123456  1                              00202310242023021520230315U1234567802         99                    alice                                             paul                               2200001011                                                                                                                                                                                I0000000{0000000{0000000{0000000{000000000{000000000{0000030{000000000{000000000{20230215                                                                                                          
8MAVEN     00000000010000000003    """


@pytest.fixture
def report_missing_from_db(employer_health_plan):
    wallet = ReimbursementWalletFactory.create(id=10827, state=WalletState.QUALIFIED)
    MemberHealthPlanFactory.create(
        reimbursement_wallet_id=wallet.id,
        reimbursement_wallet=wallet,
        employer_health_plan=employer_health_plan,
        employer_health_plan_id=employer_health_plan.id,
        subscriber_insurance_id="U12345678081111",
        patient_date_of_birth=datetime.date(2000, 1, 1),
        member_id=10000,
    )
    return """0MAVEN     Maven               160 Varick St 6th FlNew York          NY10013    2124571790UHG       2023102413:20:09T001                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                
423297100100202310241320092123456  1                              00202310242023021520230315U1234567801         99                    alice                                             paul                               2200001011                                                                                                                                                                                I0000000{0000000{0000000{0000020{000000000{000000000{0000000{000000000{000000000{20230215                                                                                                          
423297100100202310241320092123456  1                              00202310242023021520230315U1234567801         99                    alice                                             paul                               2200001011                                                                                                                                                                                I0000000{0000000{0000000{0000000{000000000{000000000{0000020{000000000{000000000{20230215                                                                                                          
423297100100202310241320092123456  1                              00202310242023021520230315U1234567808         99                    alice                                             paul                               2200001011                                                                                                                                                                                I0000000{0000000{0000000{0000000{000000000{000000000{0000020{000000000{000000000{20230215                                                                                                          
8MAVEN     00000000010000000003    """


@pytest.fixture
def report_empty():
    return """0MAVEN     Maven               160 Varick St 6th FlNew York          NY10013    2124571790UHG       2023102413:20:09T001                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                
        8MAVEN     00000000010000000003    """


@pytest.fixture(scope="function")
def report_validator(session):
    return AccumulationReportValidator(session=session)


@pytest.fixture
def uhc_file_generator_with_substring(uhc_file_generator):
    # UHC doesn't trim cardholder ids, so to test this case, we need to change that so that it does.
    # Our test data uses 11 character strings in the report and 15 character strings in the member health plans.
    # So here we'll adjust the file generator to expect that.
    uhc_file_generator.get_cardholder_id = (
        lambda member_health_plan: member_health_plan.subscriber_insurance_id[
            :11
        ].upper()
    )
    return uhc_file_generator


class TestValidatorGetWalletId:
    def test__get_wallet_id_by_subscriber_info_multiple_returned(
        self, report_validator, search_member_health_plans, logs
    ):
        error_msg = "Numerous potential wallets found for accumulation"
        assert report_validator._get_wallet_ids_as_str_by_subscriber_info(
            subscriber_id="U1234567802",
            date_of_birth=datetime.date(2000, 1, 1),
            payer_id=123456,
            report_id=2,
        ) == ["10823", "10824"]
        log = next((r for r in logs if error_msg in r["event"]), None)
        assert log is not None

    def test__get_wallet_id_by_subscriber_info_substring_subscriber_id(
        self, report_validator, search_member_health_plans
    ):
        assert report_validator._get_wallet_ids_as_str_by_subscriber_info(
            subscriber_id="U1234567804",
            date_of_birth=datetime.date(2000, 1, 1),
            payer_id=123456,
            report_id=2,
        ) == ["10825"]

    def test__get_wallet_id_by_subscriber_payer_dob(
        self, report_validator, validate_member_health_plans
    ):
        assert report_validator._get_wallet_ids_as_str_by_subscriber_info(
            subscriber_id="U1234567801",
            date_of_birth=datetime.date(2000, 1, 1),
            payer_id=123456,
            report_id=2,
        ) == ["10823"]

    def test__get_wallet_id_by_subscriber_payer_dob_invalid(
        self,
        report_validator,
        validate_member_health_plans,
        employer_health_plan,
        logs,
    ):
        MemberHealthPlanFactory.create(
            reimbursement_wallet_id=10825,
            reimbursement_wallet=ReimbursementWalletFactory.create(
                id=10825, state=WalletState.QUALIFIED
            ),
            employer_health_plan=employer_health_plan,
            employer_health_plan_id=1,
            subscriber_insurance_id="U1234567801",
            patient_date_of_birth=datetime.date(2000, 1, 1),
        )
        num_err_msg = "Numerous potential wallets found for accumulation"
        no_err_msg = "Numerous potential wallets found for accumulation"
        assert report_validator._get_wallet_ids_as_str_by_subscriber_info(
            subscriber_id="U1234567801",
            date_of_birth=datetime.date(2000, 1, 1),
            payer_id=123456,
            report_id=2,
        ) == ["10823", "10825"]
        num_log = next((r for r in logs if num_err_msg in r["event"]), None)
        assert num_log is not None
        assert (
            report_validator._get_wallet_ids_as_str_by_subscriber_info(
                subscriber_id="U1802",
                date_of_birth=datetime.date(2000, 1, 1),
                payer_id=123456,
                report_id=2,
            )
            == []
        )
        no_log = next((r for r in logs if no_err_msg in r["event"]), None)
        assert no_log is not None


class TestAccumulationReportValidator:
    def test_get_member_sums_from_db(
        self,
        report_validator,
        uhc_file_generator,
        validate_member_health_plans,
        validate_accumulation_mappings,
    ):
        member_sums = report_validator.get_member_sums_from_db(
            file_generator=uhc_file_generator, report_id=2
        )
        assert member_sums["20000101U1234567801"].deductible == 200
        assert member_sums["20000101U1234567801"].oop_applied == 200
        assert member_sums["20000101U1234567801"].cardholder_id == "U1234567801"
        assert member_sums["20000101U1234567801"].date_of_birth == datetime.date(
            year=2000, month=1, day=1
        )

        assert member_sums["20000101U1234567802"].deductible == 300
        assert member_sums["20000101U1234567802"].oop_applied == 300
        assert member_sums["20000101U1234567802"].cardholder_id == "U1234567802"
        assert member_sums["20000101U1234567802"].date_of_birth == datetime.date(
            year=2000, month=1, day=1
        )

    def test_get_member_sums_from_report(
        self, report_validator, uhc_file_generator, report_equal_length_valid
    ):
        member_sums = report_validator.get_member_sums_from_raw_report(
            raw_report=report_equal_length_valid,
            file_generator=uhc_file_generator,
            report_id=2,
        )
        assert member_sums["20000101U1234567801"].deductible == 200
        assert member_sums["20000101U1234567801"].oop_applied == 200
        assert member_sums["20000101U1234567801"].cardholder_id == "U1234567801"
        assert member_sums["20000101U1234567801"].date_of_birth == datetime.date(
            year=2000, month=1, day=1
        )

        assert member_sums["20000101U1234567802"].deductible == 300
        assert member_sums["20000101U1234567802"].oop_applied == 300
        assert member_sums["20000101U1234567802"].cardholder_id == "U1234567802"
        assert member_sums["20000101U1234567802"].date_of_birth == datetime.date(
            year=2000, month=1, day=1
        )

    def test_report_member_sums_invalid(
        self,
        report_validator,
        uhc_file_generator,
        validate_payer_report,
        validate_member_health_plans,
        validate_accumulation_mappings,
        report_equal_length_invalid,
    ):
        with testing.capture_logs() as logs:
            report_validator.validate_report_member_sums(
                report=validate_payer_report,
                raw_report=report_equal_length_invalid,
                file_generator=uhc_file_generator,
            )
        assert logs == [
            {
                "db_deductible_sum": 200,
                "db_oop_sum": 200,
                "error_detail": "Data in the db and data in the report do not match.",
                "event": "Mismatched Payer Accumulation Data",
                "log_level": "error",
                "report_deductible_sum": 10100,
                "report_id": "2",
                "report_oop_sum": 10000,
                "wallet_ids": ["10823"],
            },
        ]

    def test_report_valid(
        self,
        report_validator,
        uhc_file_generator,
        validate_payer_report,
        validate_member_health_plans,
        validate_accumulation_mappings,
        report_equal_length_valid,
    ):
        with testing.capture_logs() as logs:
            report_validator.validate_report_member_sums(
                report=validate_payer_report,
                raw_report=report_equal_length_valid,
                file_generator=uhc_file_generator,
            )
        assert logs == []

    def test_validate_data_in_db_not_report(
        self,
        report_validator,
        uhc_file_generator,
        validate_payer_report,
        validate_member_health_plans,
        validate_accumulation_mappings,
        employer_health_plan,
        report_equal_length_valid,
    ):
        # Add an extra mapping to the db
        MemberHealthPlanFactory.create(
            reimbursement_wallet_id=10826,
            reimbursement_wallet=ReimbursementWalletFactory.create(
                id=10826, state=WalletState.QUALIFIED
            ),
            employer_health_plan=employer_health_plan,
            employer_health_plan_id=employer_health_plan.id,
            subscriber_insurance_id="U1234567809",
            patient_date_of_birth=datetime.date(2000, 1, 1),
            member_id=12345,
        )
        procedure = TreatmentProcedureFactory.create(
            uuid=TP_UUID_4,
            reimbursement_wallet_id=10826,
            member_id=12345,
        )
        AccumulationTreatmentMappingFactory.create(
            treatment_procedure_uuid=procedure.uuid,
            treatment_accumulation_status=TreatmentAccumulationStatus.PROCESSED,
            deductible=100,
            oop_applied=100,
            report_id=validate_payer_report.id,
        )

        with testing.capture_logs() as logs:
            report_validator.validate_report_member_sums(
                report=validate_payer_report,
                raw_report=report_equal_length_valid,
                file_generator=uhc_file_generator,
            )
        assert logs == [
            {
                "error_detail": "Data in the db, but not in the report.",
                "event": "Mismatched Payer Accumulation Data",
                "log_level": "error",
                "report_id": f"{validate_payer_report.id}",
                "wallet_ids": ["10826"],
            }
        ]

    def test_validate_data_in_report_not_db(
        self,
        report_validator,
        uhc_file_generator,
        validate_payer_report,
        validate_member_health_plans,
        validate_081_mappings,
        report_missing_from_db,
    ):
        with testing.capture_logs() as logs:
            report_validator.validate_report_member_sums(
                report=validate_payer_report,
                raw_report=report_missing_from_db,
                file_generator=uhc_file_generator,
            )
        assert logs == [
            {
                "error_detail": "Data in the report, but not in the db.",
                "event": "Mismatched Payer Accumulation Data",
                "log_level": "error",
                "report_id": f"{validate_payer_report.id}",
                "wallet_ids": ["10827"],
            }
        ]

    def test_validate_empty_report(
        self,
        report_validator,
        uhc_file_generator,
        validate_payer_report,
        validate_member_health_plans,
        validate_accumulation_mappings,
        report_empty,
    ):
        with testing.capture_logs() as logs:
            report_validator.validate_report_member_sums(
                report=validate_payer_report,
                raw_report=report_empty,
                file_generator=uhc_file_generator,
            )
        expected_logs = [
            {
                "error_detail": "Data in the db, but not in the report.",
                "event": "Mismatched Payer Accumulation Data",
                "log_level": "error",
                "report_id": f"{validate_payer_report.id}",
                "wallet_ids": ["10823"],
            },
            {
                "error_detail": "Data in the db, but not in the report.",
                "event": "Mismatched Payer Accumulation Data",
                "log_level": "error",
                "report_id": f"{validate_payer_report.id}",
                "wallet_ids": ["10824"],
            },
        ]
        assert len(logs) == len(expected_logs)
        for log in expected_logs:
            assert log in logs

    def test_validate_report_with_empty_db(
        self,
        report_validator,
        uhc_file_generator,
        validate_payer_report,
        validate_member_health_plans,
        report_equal_length_valid,
    ):
        with testing.capture_logs() as logs:
            report_validator.validate_report_member_sums(
                report=validate_payer_report,
                raw_report=report_equal_length_valid,
                file_generator=uhc_file_generator,
            )
        expected_logs = [
            {
                "error_detail": "Data in the report, but not in the db.",
                "event": "Mismatched Payer Accumulation Data",
                "log_level": "error",
                "report_id": f"{validate_payer_report.id}",
                "wallet_ids": ["10824"],
            },
            {
                "error_detail": "Data in the report, but not in the db.",
                "event": "Mismatched Payer Accumulation Data",
                "log_level": "error",
                "report_id": f"{validate_payer_report.id}",
                "wallet_ids": ["10823"],
            },
        ]
        assert len(logs) == len(expected_logs)
        for log in expected_logs:
            assert log in logs

    def test__compare_report_to_db_caps_insensitive(
        self,
        report_validator,
        validate_payer_report,
        report_equal_length_valid,
        uhc_file_generator,
        validate_member_health_plans,
        validate_accumulation_mappings,
        db,
    ):
        # report expects uppercase such as U1234567801
        # here we prove that having lowercase in the mhp does not cause an issue
        for health_plan in validate_member_health_plans:
            health_plan.subscriber_insurance_id = (
                health_plan.subscriber_insurance_id.lower()
            )
            db.session.add(health_plan)
            db.session.commit()

        with testing.capture_logs() as logs:
            report_validator.validate_report_member_sums(
                report=validate_payer_report,
                raw_report=report_equal_length_valid,
                file_generator=uhc_file_generator,
            )
        assert logs == []

    def test_validate_report_subscriber_id_substring_valid(
        self,
        report_validator,
        validate_payer_report,
        report_equal_length_valid,
        uhc_file_generator_with_substring,
        validate_member_health_plans_substring,
        validate_accumulation_mappings,
    ):
        with testing.capture_logs() as logs:
            report_validator.validate_report_member_sums(
                report=validate_payer_report,
                raw_report=report_equal_length_valid,
                file_generator=uhc_file_generator_with_substring,
            )
        assert logs == []
